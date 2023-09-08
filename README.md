# Minnesota SLA Compliance Summary - Reporting Automation

## Overview

**Minnesota SLA Compliance Summary** is a reporting automation tool designed to calculate and report SLA compliance summary metrics on a monthly basis. The tool aims to streamline the creation of reports, adhere to a predictable schedule, and provide increased transparency to the state.

## Prerequisites

**No prerequisites or system requirements are needed.**

## Setup and Installation

Since there is no specific setup or installation process required, this tool will be delivered to internal HHA stakeholders for further delivery to external state stakeholders.

## Usage

**The script runs once a month, specifically on the 3rd of each month at 8am EST. Reports are generated and sent via email.**

## SLAs Tested
### Responsiveness and Timeliness

For each ticket type (P1, P2, P3, P4), the following SLAs are considered:

Responsiveness
- **P1** - - **P4**: Responded to inquiry within 1 business day of receipt or less

Timeliness
- **P1** - - **P4**: Resolved withn 3 business days of receipt or less

### SLA Metric Calculations

- **Responsiveness:** The responsiveness metric is calculated as the ratio of created JIRA issues that meet the SLA requirements for responsiveness to the total number of unique issues created in the specified reporting month

- **Timeliness:**: The timeliness metric is calculated as the ratio of created JIRA issues that meet the SLA requirements for timeliness to the total number of unique issues created in the specified reporting month

- **Issue Count:** The issue count is determined by the unique number of JIRA issues created, categorized by both reporting month and priority level

## Known Issues

**No known issues at the moment.**

## Contacts

For any questions or inquiries, please contact the internal HHA stakeholders.
