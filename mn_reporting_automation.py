#Import modules
import pandas as pd
import numpy as np
import pytz
import boto3
import json
import os
from datetime import datetime,timedelta,timezone
from dateutil.relativedelta import relativedelta
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import snowflake.connector
from sqlalchemy import create_engine
from decimal import Decimal
from requests.auth import HTTPBasicAuth
from openpyxl.utils import get_column_letter
import urllib
import shutil
import smtplib
import openpyxl
from openpyxl.drawing.image import Image as XLSXImage
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import ssl
from PIL import Image, ImageDraw, ImageFont
import matplotlib.gridspec as gridspec

#Fetch data from JIRA API
jira_url = "https://hhaxsupport.atlassian.net"
api_endpoint = "/rest/api/3/search"

jql_query = 'project = "Customer Service Desk" and ("HHAX Platform Region Tag" ~ MN OR "Primary Location" ~ MN OR "HHAX Market" ~ MN)'

with open('C:\\Users\\mdunlap\\Desktop\\Minnesota SLA Automation\\Secrets\jira_apikey.txt', 'r') as jira_api_key_temp:
    jira_api_key = jira_api_key_temp.read().replace('\n', '')

with open('C:\\Users\\mdunlap\\Desktop\\Minnesota SLA Automation\\Secrets\jira_email.txt', 'r') as jira_login_temp:
    jira_login = jira_login_temp.read().replace('\n', '')

jql_query_encoded = urllib.parse.quote(jql_query)

startAt = 0
maxResults = 100

all_issues = [] 
while True:
    api_url = f"{jira_url}{api_endpoint}?jql={jql_query_encoded}&startAt={startAt}&maxResults={maxResults}"

    response = requests.get(
        api_url,
        auth=HTTPBasicAuth(jira_login, jira_api_key),
        headers={
            "Accept": "application/json"
        }
    )

    json_response = response.json()

    if response.status_code == 200:
        all_issues.extend(json_response['issues'])
        
        if json_response['total'] == len(all_issues):
            break
        else:
            
            startAt += maxResults
    else:
        break


#Parse JSON payload from JIRA, extract the fields needed to calculate SLAs
if isinstance(json_response, str):
    json_response = json.loads(json_response)

issues = all_issues

if isinstance(issues, list):
    data = []

    for issue in issues:

        #Extract issue Key, determine if Provider is a VIP
        key = issue['key']
        customfield_10203_obj = issue['fields'].get('customfield_10203', {})

        if isinstance(customfield_10203_obj, dict) and 'toString' in customfield_10203_obj:

             VIP = customfield_10203_obj['toString']

        else:

            VIP = 'No'

        #Determine which elapsedTime value to use
        if VIP == 'Yes':

            customfield_10057_obj = issue['fields'].get('customfield_10057', {})
            completed_cycles_response_vip = customfield_10057_obj.get('completedCycles', [])
            if completed_cycles_response_vip:  
                completed_cycles_response_adjusted = completed_cycles_response_vip[0].get('elapsedTime', {}).get('millis', None)
            else:
                completed_cycles_response_adjusted = None
        else:
            customfield_10031_obj = issue['fields'].get('customfield_10031', {})
            completed_cycles_response = customfield_10031_obj.get('completedCycles', [])
            if completed_cycles_response:  
                completed_cycles_response_adjusted = completed_cycles_response[0].get('elapsedTime', {}).get('millis', None)
            else:
                completed_cycles_response_adjusted = None

        if VIP == 'Yes':

            customfield_10056_obj = issue['fields'].get('customfield_10056', {})
            completed_cycles_resolved_vip = customfield_10056_obj.get('completedCycles', [])
            if completed_cycles_resolved_vip:  
                completed_cycles_resolved_adjusted = completed_cycles_resolved_vip[0].get('elapsedTime', {}).get('millis', None)
            else:
                completed_cycles_resolved_adjusted = None

        else:

            customfield_10030_obj = issue['fields'].get('customfield_10030', {})
            completed_cycles_resolved = customfield_10030_obj.get('completedCycles', [])
            if completed_cycles_resolved:  
                completed_cycles_resolved_adjusted = completed_cycles_resolved[0].get('elapsedTime', {}).get('millis', None)
            else:
                completed_cycles_resolved_adjusted = None
        priority_obj = issue['fields'].get('priority', {})
        priority_name = priority_obj.get('name', None)
        created = issue['fields'].get('created', None)
        status_snapshot = issue['fields'].get('status', {}).get('name', None)

        #Append extracted data to data list object
        data.append([key, VIP,completed_cycles_response_adjusted,completed_cycles_resolved_adjusted,priority_name,created,status_snapshot])


    #Convert data list to pandas dataframe
    df = pd.DataFrame(data, columns=['key', 'VIP','elapsed_time_response','elapsed_time_resolved','priority_name','created', 'status_snapshot'])


#Convert 'created' column to timestamp dataset from string.  Get the current date, month, and year
df['created'] = pd.to_datetime(df['created'],utc=True)
current_date = datetime.now()
current_month = current_date.month
current_year = current_date.year

#Omit rows with the created dates greater than the reporting month
temp_filtered_df = df[(df['created'].dt.month != current_month) | (df['created'].dt.year != current_year)]

#Error handling -- user forgets to input priority_name, assume it is lowest priority
temp_filtered_df.loc[temp_filtered_df['priority_name'] == 'P5- Awaiting Assignment', 'priority_name'] = 'P4- Low'

#Convert time responses from milliseconds to hours for use in SLA compliance functions, store in datafream
temp_filtered_df['elapsed_time_response_hours'] = temp_filtered_df['elapsed_time_response'] / 3600000  # 3,600,000 milliseconds in an hour
temp_filtered_df['elapsed_time_resolved_hours'] = temp_filtered_df['elapsed_time_resolved'] / 3600000  # 3,600,000 milliseconds in an hour

#Data cleanup
temp_filtered_df = temp_filtered_df.dropna(subset=['elapsed_time_response_hours'])

#Build function to determine row level SLA response compliance, call function and append results to new dataframe
def SLA_First_Response(temp_filtered_df):
    def check_SLA_response(row):
        priority = row['priority_name']
        elapsed_time = row['elapsed_time_response_hours']

        if priority in ['P1- Highest', 'P2- High','P3- Medium', 'P4- Low'] and elapsed_time <= 24:
            return 'Yes'
        else:
            return 'No'
        
    temp_filtered_df['SLA_First_Response_Results'] = temp_filtered_df.apply(check_SLA_response, axis=1)
    return sla_df

sla_df = temp_filtered_df.copy()
sla_df = SLA_First_Response(sla_df)

 
#Build function to determine row level SLA resolved compliance, call function and append results to dataframe created in previous step
def SLA_Issue_Resolved(sla_df):
    def check_SLA_resolved(row):            
        priority = row['priority_name']
        elapsed_time = row['elapsed_time_resolved_hours']

        if pd.isna(elapsed_time):
            return 'N/A'
        elif priority in ['P1- Highest','P2- High','P3- Medium', 'P4- Low'] and elapsed_time <= 72:
            return 'Yes'
        else:
            return 'No'

    sla_df['SLA_First_Resolved_Results'] = sla_df.apply(check_SLA_resolved, axis=1)
    return sla_df

sla_df_final = sla_df.copy()
sla_df_final = SLA_Issue_Resolved(sla_df_final)

#Convert the 'created' column to datetime, keeping the original time zone offset
sla_df_final['created'] = pd.to_datetime(sla_df_final['created'], utc=True)

#Convert the 'created' column to Eastern Time
sla_df_final['created'] = sla_df_final['created'].dt.tz_convert('US/Eastern')

#Create new 'created_month_year' column, which will serve as column headers
sla_df_final['created_month_year'] = sla_df_final['created'].dt.to_period('M')

#Extract the priority number from 'priority_name' field
sla_df_final['priority_number'] = sla_df_final['priority_name'].str.extract('(\d+)')[0]

#Begin the time series in June 2022 
sla_df_final_filtered = sla_df_final[sla_df_final['created_month_year'] >= '2022-06']

#Pivot table so that the created_month_year are the column headers, with priority_number as the dataframe index
pivoted_df = pd.pivot_table(sla_df_final_filtered,

                          values='key',

                          index='priority_number',

                          columns='created_month_year',

                          aggfunc='count',

                          fill_value=0)

 
#Data Cleanup
pivoted_df.index = pivoted_df.index.astype(int)

if 1 not in pivoted_df.index:

    pivoted_df.loc[1] = [0]*len(pivoted_df.columns)

pivoted_df.sort_index(inplace=True)

 
#Count 'Yes' for SLA_First_Response_Results and SLA_First_Resolved_Results, store in dataframe
response_yes = sla_df_final_filtered[sla_df_final_filtered['SLA_First_Response_Results'] == 'Yes'].groupby('created_month_year').size()
resolve_yes = sla_df_final_filtered[sla_df_final_filtered['SLA_First_Resolved_Results'] == 'Yes'].groupby('created_month_year').size()

#Count all tickets
total_tickets = sla_df_final_filtered.groupby('created_month_year').size()

#Calculate timeliness values
response_percent = (response_yes / total_tickets) * 100
resolve_percent = (resolve_yes / total_tickets) * 100

#Reformat the pandas series to DataFrame
final_df = pd.DataFrame({
    'First Response Percent': response_percent.round(1),
    'First Resolve Percent': resolve_percent.round(1)
}).transpose()


#Data Cleanup/Formatting tweaks
final_df = final_df.applymap(lambda x: f"{x}%")
pivoted_reset = pivoted_df.reset_index()
final_df.columns = pivoted_df.columns

#Rename index of final_df to have labels "First Response" and "Resolved"
final_df['priority_number'] = ['First Response', 'Resolved']

#Concatenate pivoted_df and final_df dataframes vertically

combined_df = pd.concat([pivoted_reset, final_df], ignore_index=True)
combined_df.reset_index(drop=True, inplace=True)

# Step 3: Update the 'First Response' and 'Resolved' rows in 'combined_df'
first_response_index = combined_df[combined_df['priority_number'] == 'First Response'].index[0]
resolved_index = combined_df[combined_df['priority_number'] == 'Resolved'].index[0]

#Find the row index where 'First Response' is located
first_response_row = combined_df[combined_df['priority_number'] == 'First Response']
resolved_row = combined_df[combined_df['priority_number'] == 'Resolved']

#Remove these rows from the original dataframe, apppend again later
filtered_df = combined_df[~combined_df['priority_number'].isin(['First Response', 'Resolved'])]

#Convert all numeric columns to their proper data type
for col in filtered_df.columns:
    if col != 'priority_number':
        filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce')

#Calculate the total row
total_row = filtered_df.drop(columns=['priority_number']).sum(numeric_only=True)

#Create a DataFrame for the 'Tttal' row
total_df = pd.DataFrame([['Total'] + total_row.tolist()], columns=filtered_df.columns)

#Concatenate the original dataframe and the 'Tttal' row
new_df = pd.concat([filtered_df, total_df], ignore_index=True)
#Add back 'First Response' and 'Resolved' rows, store in a final_df
final_df_2 = pd.concat([new_df, first_response_row, resolved_row], ignore_index=True)

#Save CSV into directory
final_df_2.to_csv("MN_SLA_Compliance_Monthly_Report.csv",index=False)

#Build Email server

#Get Last Month for email formatting
get_today = datetime.now()
last_month_date = get_today - relativedelta(months=1)
formatted_date = last_month_date.strftime("%B-%Y")

smtp_port = 587
smtp_server = "smtp.gmail.com"

#Load Some Secrets
with open('C:\\Users\\mdunlap\\Desktop\\Minnesota SLA Automation\\Secrets\\hha email - from.txt', 'r') as from_email2:
    from_email = from_email2.read().replace('\n', '')
    
email_from = from_email

#with open('C:\\Users\\mdunlap\\Desktop\\Minnesota SLA Automation\\Secrets\\hha email - to.txt', 'r') as to_email_project:
    #to_email = to_email_project.read().strip().split(',')
    
#email_members = to_email

#', '.join(email_members_2)

with open('C:\\Users\\mdunlap\\Desktop\\Minnesota SLA Automation\\Secrets\\google app password.txt', 'r') as app_pass:
    google_pass = app_pass.read().replace('\n', '')

google_password = google_pass

email_members = 'mdunlap@hhaexchange.com'

def send_compliance_report(email_members):
    subject = 'MN SLA Compliance Monthly Report' + ' '+ '-' + ' ' + formatted_date

    body = 'MN SLA Compliance Status Update as of month end ' + ' ' + formatted_date + '.'
    
    msg = MIMEMultipart()
    msg['From'] = email_from
    msg['To'] = 'mdunlap@hhaexchange.com'
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    with open("MN_SLA_Compliance_Monthly_Report.csv", "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename=MN_SLA_Compliance_Monthly_Report.csv")
        msg.attach(part)

    text = msg.as_string()

    mail_server = smtplib.SMTP(smtp_server, smtp_port)
    mail_server.starttls()
    mail_server.login(email_from, google_password)
    mail_server.sendmail(email_from, email_members, text)
    mail_server.quit()

send_compliance_report(email_members)