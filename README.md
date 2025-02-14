[comment]: # "Auto-generated SOAR connector documentation"
# Tanium REST

Publisher: Splunk  
Connector Version: 2\.1\.5  
Product Vendor: Tanium  
Product Name: Tanium REST  
Product Version Supported (regex): "\.\*"  
Minimum Product Version: 5\.1\.0  

This app supports investigative and generic actions on Tanium

[comment]: # " File: README.md"
[comment]: # "  Copyright (c) 2019-2022 Splunk Inc."
[comment]: # "  Licensed under the Apache License, Version 2.0 (the 'License');"
[comment]: # "  you may not use this file except in compliance with the License."
[comment]: # "  You may obtain a copy of the License at"
[comment]: # ""
[comment]: # "      http://www.apache.org/licenses/LICENSE-2.0"
[comment]: # ""
[comment]: # "  Unless required by applicable law or agreed to in writing, software distributed under"
[comment]: # "  the License is distributed on an 'AS IS' BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,"
[comment]: # "  either express or implied. See the License for the specific language governing permissions"
[comment]: # "  and limitations under the License."
[comment]: # ""
[comment]: # " pragma: allowlist secret "
## Playbook Backward Compatibility

-   The existing action parameters have been modified for the action given below. Hence, it is
    requested to the end-user to please update their existing playbooks by re-inserting \| modifying
    \| deleting the corresponding action blocks or by providing appropriate values to these action
    parameters to ensure the correct functioning of the playbooks created on the earlier versions of
    the app.

      

    -   Run Query - 3 new action parameters 'wait_for_results_processing',
        'return_when_n\_results_available', 'wait_for_n\_results_available' are added which helps to
        limit the data fetched from the Tanium server.

-   New action 'Get Question Results' has been added. Hence, it is requested to the end-user to
    please update their existing playbooks by inserting the corresponding action blocks for this
    action on the earlier versions of the app.

## Port Information

The app uses HTTP/ HTTPS protocol for communicating with the Tanium server. Below are the default
ports used by Splunk SOAR.

|         Service Name | Transport Protocol | Port |
|----------------------|--------------------|------|
|         http         | tcp                | 80   |
|         https        | tcp                | 443  |

## Asset Configuration

-   **Consider question results complete at (% out of 100)**

      

    -   Consider Tanium question results complete at this value, a percentage out of 100. This
        parameter impacts the **run query** and **list processes** actions only. Note that a similar
        value can be defined in Tanium user preferences – you might want to reflect the same value
        in your app asset configuration as you use in your Tanium user configuration. The time spent
        returning your results is dependent on how much data you have on your Tanium instance and
        you may want your action to end with a certain percentage threshold instead of waiting for
        Tanium to return 100% of the results.

-   **API Token**

      

    -   An API token can be used for authentication in place of the basic auth method of username
        and password. If the asset is configured with **both** API token and username/password
        credentials, the token will be used as the preferred method. However for security purposes,
        once the token has expired or if it is invalid, the app will **NOT** revert to basic auth
        credentials - the token must either be removed from or replaced in the asset config.

## API Token Generation

-   There are different methods of creating an API token depending on which version of Tanium is
    being used. Later versions allow token generation through the UI, while earlier versions require
    the use of curl commands.

-   **IMPORTANT: The default expiration of a generated token is 7 days. To reduce maintenance, we
    recommend setting the default expiration to 365 days. Note that you will have to repeat this
    process to generate a new token before the current token expires. Failure to do so will cause
    integration to break as your token will no longer be valid after such date.**

-   **The end user will need to add the SOAR source IP address as a "Trusted IP Address" when
    creating a Tanium API Token. They will also need to note the expiration time and create a new
    token accordingly.**

-   **The following information regarding API calls using curl commands and additional notes have
    been taken from the "Tanium Server REST API Reference" documentation. More information can be
    gathered by contacting Tanium Support.**

      

    ### UI

-   To generate an API token in the UI and to configure the system to use it, please follow the
    steps mentioned in this
    [documentation](https://docs.tanium.com/platform_user/platform_user/console_api_tokens.html) .
    On Tanium 7.5.2.3503, new API tokens can be generated by selecting Administration \> Permissions
    \> API Tokens \> New API Token. Depending on the version of Tanium, the UI may not contain the
    token creation button on the page and will only display a list of the existing API tokens. If
    this is the case, you will need to use the curl command method.

      

    ### Curl

-   To generate an API token using this method, a session string or token string will need to be
    acquired first through the Login API endpoint. Then, the session or token string will be passed
    in the header to get the API token. In the examples below, fields need to be passed in the API
    token request. **You MUST include the SOAR IP address as a trusted IP address.** It is also
    useful to include the **notes** field, as this can be useful in identifying the token after it
    is created since the token string is not visible in the UI using this method.

-   #### Login API Endpoint

      
    `       /api/v2/session/login      `

    #### Example Request

    `       $ curl -s -X POST --data-binary @sample_login.json https://localhost/api/v2/session/login      `

              # where sample_login.json contains:
              # {
              #   "username": "jane.doe",
              #   "domain": "dev",
              #   "password": "JanesPassword" 
              # }
              

    #### Example Response

              {
                "data": {
                    "session": "1-224-3cb8fe975e0b505045d55584014d99f6510c110d19d0708524c1219dbf717535"
                    }
              }
                

-   #### Token API Endpoint

      
    `       /api/v2/api_tokens      `

    #### Example Request (session string):

    `       $ curl -s -X POST -H "session:{string}" --data "{json object}" https://localhost/api/v2/api_tokens      `

    #### Header Parameters

    | Field   | Type   | Description                                                                                                      |
    |---------|--------|------------------------------------------------------------------------------------------------------------------|
    | session | string | (Required) The Tanium session or token string. The session string is returned by the Log In and Validate routes. |

    #### Body Parameters

    | Field  | Type             | Description                                                                                                                                                                         |
    |--------|------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
    | object | application/json | (Required) A json object containing fields "expire_in_days", "notes", and "trusted_ip_addresses". Be sure that the SOAR IP address is included in the "trusted_ip_addresses" field. |

    #### Example Request (with fields):

    `       $ curl -s -X POST -H "session:{string}" --data-binary @new_token.json https://localhost/api/v2/api_tokens      `

              # where new_token.json contains:
              # {
              #   "expire_in_days": 365,
              #   "notes": "My module token.",
              #   "trusted_ip_addresses": "10.10.10.15,192.168.3.0/24"
              # }
                

## Permissions for Interacting with Tanium REST API

-   **Actions may fail if the account you are using to connect to Tanium does not have sufficient
    permissions.**

      
      

<!-- -->

-   Computer Groups

      

    -   A component of Tanium permissions is the “Computer Groups” which an account can operate on.
        Please ensure the account you used to configure the Tanium REST API app has access to any
        machines you run queries or actions on.

      

-   Suggested Roles for Phantom Account in Tanium

      

    -   The following Tanium Roles shown below can be configured within Tanium and applied to the
        account used to connect to Phantom. Note that these roles represent guidance by the Splunk
        Phantom team based on testing against Tanium 7.3.314. **The permissions required in your
        environment may vary.**

    -   On Tanium 7.3.314, roles can be configured by selecting Permissions \> Roles in the Tanium
        UI. Roles can be applied to a user account by selecting Administration \> Users \> (View
        User) \> Edit Roles in the Tanium UI.

    -   Alternatively, you can **Import from XML** directly under Permissions \> Roles in the Tanium
        UI. The XML files containing the roles described below are attached to this app's folder.

          
          
        `                     Role #1 Name:                    Phantom All Questions         `

        -   `                         Permissions:                        Can Ask Question and Saved Question. Needed for run query and list processes actions.           `
        -   `                         Ask Dynamic Question:                        Yes           `
        -   `                         Show Interact:                        Yes           `
        -   `                         Advanced Permissions:                        Read Sensor, Read Saved Question           `

        `                               Role #2 Name:                    Phantom Actions         `

        -   `                         Permissions:                        Can execute actions only. Needed for execute action and terminate process.           `
        -   `                         Show Interact:                        Yes           `
        -   `                         Advanced Permissions:                        Read Action, Write Action, Read Package           `

## Pagination

-   Pagination is not implemented in this release. So, the results for the actions mentioned below
    will be the results that are fetched in a single API call.

      

    -   List processes
    -   List questions
    -   Run query

## How to use Run Query Action

-   The **Run Query** action uses **Tanium's Interact Question Bar** to ask questions to retrieve
    information from endpoints. For example, you can ask a question that determines whether any
    endpoints are missing critical security patches.

-   Parameter Information:  
    These parameters modify questions asked using one of the two modes of operation specified below.
    -   **wait_for_results_processing:** Some long-running sensors return intermediate results with
        the contents "results currently unavailable", and then [later the sensor fills in the
        results](https://docs.tanium.com/interact/interact/results.html#:~:text=Results%20Currently%20Unavailable)
        . This option instructs the App to wait until the results are returned to Tanium and only
        after that return the final results. The waiting is still time bounded by the
        **timeout_seconds** setting.
    -   **return_when_n\_results_available:** When set, the Tanium REST App will return results to
        the playbook as soon as \`N\` results are returned, even if the **Consider question results
        complete at (% out of 100)** percentage has not been met. This is useful in scenarios where
        the playbook expects to get at most \`N\` results, and wants to return as soon as this
        occurs.
    -   **wait_for_n\_results_available:** When set, the Tanium REST App will wait (up to the
        **timeout_seconds** timeout) until at least \`N\` results are returned. This is helpful in
        situations where the Tanium server is under high utilization. Sometimes the App will
        estimate that 100% of hosts have reported results, even when there are a few stragglers
        left. If the playbook author knows that it should be getting \`N\` results, this will wait
        past the **Consider question results complete at (% out of 100)** percentage.

-   Two modes of operation are supported for the run query action:

      
      

    -   Manual Questions
        -   Using Tanium question syntax, users can directly provide the question to be asked to the
            Tanium server in the **query_text** parameter. For more information on Tanium's question
            syntax, [click here.](https://docs.tanium.com/interact/interact/questions.html)

        -   Make sure the **is_saved_question** box is unchecked since you are providing a question
            from scratch.

        -   Use the **group name** parameter to run your query on a particular computer group in
            your Tanium instance. Users can create a computer group with specific IP
            addresses/hostnames on the Tanium UI under Administration>Computer Groups. For a guide
            on how to create/manage computer groups in Tanium, [click
            here.](https://docs.tanium.com/platform_user/platform_user/console_computer_groups.html)

              

            -   NOTE: If the **group_name** parameter is not provided, the query will be executed on
                all registered IP addresses/hostnames in your Tanium instance.

              

        -   Parameterized Query

              

            -   Users can provide the parameter(s) of a Parameterized query in square
                brackets(\[parameter-1, parameter-2, ..., parameter-n\]).

                  

                -   Example: Get Process Details\["parameter-1","parameter-2"\] from all machines
                    with Computer Name contains localhost

            -   Users can ignore the parameter part in the query if they want the default value to
                be considered. Below are the 2 ways a user can achieve this:

                  

                -   Query: Get Process Details from all machines with Computer Name contains
                    localhost
                -   Query: Get Process Details\["",""\] from all machines with Computer Name
                    contains localhost

            -   If a user wants to add only one parameter out of two parameters, users can keep the
                parameter empty. Below are the examples:

                  

                -   Example: Get Process Details\["parameter-1",""\] from all machines with Computer
                    Name contains localhost
                -   Example: Get Process Details\["","parameter-2"\] from all machines with Computer
                    Name contains localhost

            -   For two or more sensors in a query, users can select one of the below:

                  

                -   Provide value for all the parameters of all the sensors in the query

                      

                    -   Example: Get Child Processes\["parameter-1"\] and Process
                        Details\["parameter-2","parameter-3"\] from all machines

                -   Do not provide value for any of the parameters of any of the sensors in the
                    query

                      

                    -   Example: Get Child Processes and Process Details from all machines

                -   Provide value for the parameters you want to provide. The parameters for which
                    you don't want to add value, please use double quotes("")

                      

                    -   Example: Get Child Processes\[""\] and Process Details\["SHA1", ""\] from
                        all machines
                    -   Example: Get Child Processes\["csrss.exe"\] and Process Details\["", ""\]
                        from all machines

                  

            -   Scenarios:

                  

                1.  If the Child Processes sensor expects 1 parameter and Process Details expects 2
                    parameters. But the user provides only 2 parameters instead of 3, then action
                    will fail with a proper error message.
                    -   Example: Get Child Processes\["parameter-1"\] and Process
                        Details\["parameter-2"\] from all machines
                2.  If the Child Processes sensor expects 1 parameter and Process Details expects 2
                    parameters. But the user provides more than 3 parameters, then action will fail
                    with a proper error message.
                    -   Example: Get Child Processes\["parameter-1", "parameter-2"\] and Process
                        Details\["parameter-3", "parameter-4"\] from all machines
                3.  If the Child Processes sensor expects 1 parameter and Process Details expects 2
                    parameters. But if the user does not provide any parameter in the Child
                    Processes sensor and 3 parameters in Process Details sensor, then the first
                    parameter from Process Details will be considered as the only parameter of the
                    Child Processes sensor and the action will fetch the results accordingly.
                    -   Query provided: Get Child Processes and Process Details\["parameter-1",
                        "parameter-2", "parameter-3"\] from all machines
                    -   Query that will be executed because of API limitations: Get Child
                        Processes\["parameter-1"\] and Process Details\["parameter-2",
                        "parameter-3"\] from all machines
                4.  If the Child Processes sensor expects 1 parameter and Process Details expects 2
                    parameters. But if the user provides 2 parameters in Child Processes sensor and
                    1 parameter in Process Details sensor, then the second parameter from Child
                    Processes sensor will be considered as the first parameter of the Process
                    Details sensor and the only parameter of the Process Details sensor will be
                    considered as the second parameter of the same. The action will fetch the
                    results accordingly.
                    -   Query provided: Get Child Processes\["parameter-1", "parameter-2"\] and
                        Process Details\["parameter-3"\] from all machines
                    -   Query that will be executed because of API limitations: Get Child
                        Processes\["parameter-1"\] and Process Details\["parameter-2",
                        "parameter-3"\] from all machines

        -   Example Run 1 - Get Computer Name:

              

            -   `                             query text                            : Get Computer Name from all machines             `

            -   `                             is saved question                            : False             `

            -   `                             group name                            :             `

            -   `                             timeout seconds                            : 600             `

                  
                `                             `

        -   Example Run 2 - Get Computer Name for Specified Computer Group:

              

            -   `                             query text                            : Get Computer Name from all machines             `

            -   `                             is saved question                            : False             `

            -   `                             group name                            : centos-computers             `

            -   `                             timeout seconds                            : 600             `

                  
                `                             `

        -   Example Run 3 - A Complex Query:

              

            -   `                             query text                            : Get Trace Executed Processes[1 month,1522723342293|1522726941293,0,0,10,0,rar.exe,"",-hp,"","",""] from all machines             `

            -   `                             is saved question                            : False             `

            -   `                             group name                            :             `

            -   `                             timeout seconds                            : 600             `

                  
                `                             `

        -   Example Run 4 - List Process Details for a Specified Device:

              

            -   `                             query text                            : Get Process Details["",""] from all machines with Computer Name contains localhost             `

            -   `                             is saved question                            : False             `

            -   `                             group name                            : centos-computers             `

            -   `                             timeout seconds                            : 600             `

                  
                `                             `

          

    -   Saved Questions

          

        -   Users can create 'Saved Questions' on the Tanium UI under Content>Saved Questions and
            provide the name of that saved question in the **query_text** parameter to fetch
            appropriate results. For a guide on how to create/manage the Saved Questions on your
            Tanium instance, [click
            here.](https://docs.tanium.com/interact/interact/saving_questions.html)

        -   The **is_saved_question** box must be checked for this to work correctly.

              
              

        -   Example Run:

              

            -   `                               query text                              : My Computers              `

            -   `                               is saved question                              : True              `

            -   `                               timeout seconds                              : 600              `

                  
                `                               `

  

## How to use Terminate Process Action

-   Please follow the steps below to execute this action successfully:

      

    -   Create and save a package on the Tanium server with a meaningful package name and add a
        command to terminate the required process in the package's command section.
    -   To terminate the process of particular computers, users can create a computer group with the
        IP address/hostname of the target computers and can specify that group name in the
        **group_name** parameter.
    -   If the **group_name** parameter is not provided, then the terminate process action will be
        executed on all the registered IP addresses/hostnames.

  

## How to use Execute Action

-   The 'Execute Action' action will cause a specified Tanium Package to be executed on the
    specified group.

      

    -   Create and save a package on the Tanium server with a meaningful package name and add a
        command in the package's command section, or just use an existing package.

    -   Any parameters required by the specified package must be supplied with a valid JSON via the
        **package_parameters** parameter. For example,
        `         {"$1":"Standard_Collection", "$2":"SCP"}        `

    -   To execute this action on particular computers, users can create a computer group with the
        IP address/hostname of the target computers and can specify that group name in the
        **group_name** parameter.

    -   If the **group_name** parameter is not provided, then the action will be executed on all the
        registered IP addresses/hostnames.

    -   Example Run:

          

        -   `                         action name                        : Splunk Live Response Test           `

        -   `                         action group                        : Default           `

        -   `                         package name                        : Live Response - Linux           `

        -   `                         package parameters                        : {"$1":"Standard_Collection", "$2":"SCP"}           `

        -   `                         group name                        : centos-computers           `

              
            `                         `

  


### Configuration Variables
The below configuration variables are required for this Connector to operate.  These variables are specified when configuring a Tanium REST asset in SOAR.

VARIABLE | REQUIRED | TYPE | DESCRIPTION
-------- | -------- | ---- | -----------
**base\_url** |  required  | string | Base URL \(e\.g\. https\://10\.1\.16\.94\)
**api\_token** |  optional  | password | API Token
**username** |  optional  | string | Username
**password** |  optional  | password | Password
**verify\_server\_cert** |  optional  | boolean | Verify Server Certificate
**results\_percentage** |  optional  | numeric | Consider question results complete at \(% out of 100\)

### Supported Actions  
[test connectivity](#action-test-connectivity) - Validate the asset configuration for connectivity using supplied configuration  
[list processes](#action-list-processes) - List the running processes of the devices registered on the Tanium server  
[parse question](#action-parse-question) - Parses the supplied text into a valid Tanium query string  
[list questions](#action-list-questions) - Retrieves either a history of the most recent questions or a list of saved questions  
[terminate process](#action-terminate-process) - Kill a running process of the devices registered on the Tanium server  
[execute action](#action-execute-action) - Execute an action on the Tanium server  
[run query](#action-run-query) - Run a search query on the devices registered on the Tanium server  
[get question results](#action-get-question-results) - Return the results for an already asked question  

## action: 'test connectivity'
Validate the asset configuration for connectivity using supplied configuration

Type: **test**  
Read only: **True**

#### Action Parameters
No parameters are required for this action

#### Action Output
No Output  

## action: 'list processes'
List the running processes of the devices registered on the Tanium server

Type: **investigate**  
Read only: **True**

This action requires specifying a sensor to be used to list processes\. A standard Tanium sensor, 'Process Details' is used by default but a different sensor can be specified instead\. Note that the 'Process Details' sensor may not be available on all Tanium deployments\. Note that at this time this action only supports limiting the query to specified computer groups, but a generic Run Query action can be constructed to query an in individual computer's processes\. As pagination is not implemented, the result\(s\) of the action will be the result\(s\) that are fetched in a single API call\.

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**sensor** |  required  | Sensor which will list all the processes | string | 
**group\_name** |  optional  | Computer group name of which the processes will be listed | string | 
**timeout\_seconds** |  required  | The number of seconds before the question expires | numeric | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.parameter\.group\_name | string | 
action\_result\.parameter\.sensor | string | 
action\_result\.parameter\.timeout\_seconds | numeric | 
action\_result\.data\.\*\.data\.max\_available\_age | string | 
action\_result\.data\.\*\.data\.now | string | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.age | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.archived\_question\_id | numeric |  `taniumrest question id` 
action\_result\.data\.\*\.data\.result\_sets\.\*\.cache\_id | string | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.columns\.\*\.hash | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.columns\.\*\.name | string | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.columns\.\*\.type | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.error\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.estimated\_total | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.expiration | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.expire\_seconds | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.filtered\_row\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.filtered\_row\_count\_machines | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.id | numeric |  `taniumrest question id` 
action\_result\.data\.\*\.data\.result\_sets\.\*\.issue\_seconds | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.item\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.mr\_passed | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.mr\_tested | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.no\_results\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.passed | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.question\_id | numeric |  `taniumrest question id` 
action\_result\.data\.\*\.data\.result\_sets\.\*\.report\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.row\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.row\_count\_machines | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.rows\.\*\.cid | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.rows\.\*\.data\.\*\.text | string | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.rows\.\*\.id | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.saved\_question\_id | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.seconds\_since\_issued | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.select\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.tested | numeric | 
action\_result\.status | string | 
action\_result\.message | string | 
action\_result\.summary\.num\_results | numeric | 
action\_result\.summary\.timeout\_seconds | numeric | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'parse question'
Parses the supplied text into a valid Tanium query string

Type: **investigate**  
Read only: **True**

<p>When asked a non\-saved question in the <b>query\_text</b> parameter, it will parse the given query and give a list of suggestions that are related to it\.</p><p>For example, on the Tanium platform, if one were to just ask the question, 'all IP addresses,' Tanium will give the suggestions\:<br><ul><li>Get Static IP Addresses from all machines</li><li>Get IP Routes from all machines</li><li>Get IP Address from all machines</li><li>Get IP Connections from all machines</li><li>Get IP Route Details from all machines</li><li>Get Network IP Gateway from all machines</li></ul><br>Tanium sorts this list, from most\-related to least\-related\.</p>

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**query\_text** |  required  | Query text to parse | string |  `taniumrest question text` 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.parameter\.query\_text | string |  `taniumrest question text` 
action\_result\.data\.\*\.from\_canonical\_text | numeric | 
action\_result\.data\.\*\.group | string |  `taniumrest group definition` 
action\_result\.data\.\*\.question\_text | string |  `taniumrest question text` 
action\_result\.data\.\*\.selects\.\*\.sensor\.hash | numeric | 
action\_result\.data\.\*\.selects\.\*\.sensor\.name | string | 
action\_result\.data\.\*\.sensor\_references\.\*\.name | string | 
action\_result\.data\.\*\.sensor\_references\.\*\.real\_ms\_avg | numeric | 
action\_result\.data\.\*\.sensor\_references\.\*\.start\_char | string | 
action\_result\.status | string | 
action\_result\.message | string | 
action\_result\.summary\.number\_of\_parsed\_questions | numeric | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'list questions'
Retrieves either a history of the most recent questions or a list of saved questions

Type: **investigate**  
Read only: **True**

If the <b>list\_saved\_questions</b> parameter is true, this action will return a list of saved questions\. If the flag is not set, this action will return the history of recently asked questions\. As pagination is not implemented, the result\(s\) of the action will be the result\(s\) that are fetched in a single API call\.

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**list\_saved\_questions** |  optional  | Retrieve Saved Questions | boolean | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.parameter\.list\_saved\_questions | boolean | 
action\_result\.data\.\*\.action\_tracking\_flag | boolean | 
action\_result\.data\.\*\.archive\_enabled\_flag | boolean | 
action\_result\.data\.\*\.archive\_owner | string | 
action\_result\.data\.\*\.archive\_owner\.id | numeric | 
action\_result\.data\.\*\.archive\_owner\.name | string | 
action\_result\.data\.\*\.content\_set\.id | numeric | 
action\_result\.data\.\*\.content\_set\.name | string | 
action\_result\.data\.\*\.expire\_seconds | numeric | 
action\_result\.data\.\*\.hidden\_flag | boolean | 
action\_result\.data\.\*\.id | numeric | 
action\_result\.data\.\*\.issue\_seconds | numeric | 
action\_result\.data\.\*\.issue\_seconds\_never\_flag | boolean | 
action\_result\.data\.\*\.keep\_seconds | numeric | 
action\_result\.data\.\*\.metadata\.\*\.admin\_flag | boolean | 
action\_result\.data\.\*\.metadata\.\*\.name | string | 
action\_result\.data\.\*\.metadata\.\*\.value | string | 
action\_result\.data\.\*\.mod\_time | string | 
action\_result\.data\.\*\.mod\_user\.display\_name | string | 
action\_result\.data\.\*\.mod\_user\.domain | string |  `domain` 
action\_result\.data\.\*\.mod\_user\.id | numeric | 
action\_result\.data\.\*\.mod\_user\.name | string | 
action\_result\.data\.\*\.most\_recent\_question\_id | numeric | 
action\_result\.data\.\*\.name | string | 
action\_result\.data\.\*\.packages\.\*\.id | numeric | 
action\_result\.data\.\*\.packages\.\*\.name | string | 
action\_result\.data\.\*\.public\_flag | boolean | 
action\_result\.data\.\*\.query\_text | string |  `taniumrest question text` 
action\_result\.data\.\*\.question\.id | numeric | 
action\_result\.data\.\*\.row\_count\_flag | boolean | 
action\_result\.data\.\*\.sort\_column | numeric | 
action\_result\.data\.\*\.user\.deleted\_flag | boolean | 
action\_result\.data\.\*\.user\.id | numeric | 
action\_result\.data\.\*\.user\.name | string | 
action\_result\.status | string | 
action\_result\.message | string | 
action\_result\.summary\.num\_saved\_questions | numeric | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'terminate process'
Kill a running process of the devices registered on the Tanium server

Type: **generic**  
Read only: **False**

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**action\_name** |  required  | Name of the action | string | 
**action\_group** |  required  | Group of the action | string | 
**package\_name** |  required  | Package name that will be executed | string | 
**package\_parameters** |  optional  | Package parameters of the corresponding package | string | 
**group\_name** |  optional  | Computer group name of which the process will be terminated | string | 
**distribute\_seconds** |  optional  | The number of seconds over which to deploy the action | numeric | 
**issue\_seconds** |  optional  | The number of seconds to reissue an action from the saved action | numeric | 
**expire\_seconds** |  required  | The duration from the start time before the action expires | numeric | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.parameter\.action\_group | string | 
action\_result\.parameter\.action\_name | string | 
action\_result\.parameter\.distribute\_seconds | numeric | 
action\_result\.parameter\.expire\_seconds | numeric | 
action\_result\.parameter\.group\_name | string | 
action\_result\.parameter\.issue\_seconds | numeric | 
action\_result\.parameter\.package\_name | string | 
action\_result\.parameter\.package\_parameters | string | 
action\_result\.data\.\*\.action\_group\_id | numeric | 
action\_result\.data\.\*\.approved\_flag | boolean | 
action\_result\.data\.\*\.approver\.id | numeric | 
action\_result\.data\.\*\.approver\.name | string | 
action\_result\.data\.\*\.comment | string | 
action\_result\.data\.\*\.creation\_time | string | 
action\_result\.data\.\*\.distribute\_seconds | numeric | 
action\_result\.data\.\*\.end\_time | string | 
action\_result\.data\.\*\.expire\_seconds | numeric | 
action\_result\.data\.\*\.id | numeric | 
action\_result\.data\.\*\.issue\_count | numeric | 
action\_result\.data\.\*\.issue\_seconds | numeric | 
action\_result\.data\.\*\.last\_action\.id | numeric | 
action\_result\.data\.\*\.last\_action\.start\_time | string | 
action\_result\.data\.\*\.last\_action\.target\_group\.id | numeric | 
action\_result\.data\.\*\.last\_start\_time | string | 
action\_result\.data\.\*\.name | string | 
action\_result\.data\.\*\.next\_start\_time | string | 
action\_result\.data\.\*\.package\_spec\.available\_time | string | 
action\_result\.data\.\*\.package\_spec\.command | string | 
action\_result\.data\.\*\.package\_spec\.command\_timeout | numeric | 
action\_result\.data\.\*\.package\_spec\.content\_set\.id | numeric | 
action\_result\.data\.\*\.package\_spec\.content\_set\.name | string | 
action\_result\.data\.\*\.package\_spec\.creation\_time | string | 
action\_result\.data\.\*\.package\_spec\.deleted\_flag | boolean | 
action\_result\.data\.\*\.package\_spec\.display\_name | string | 
action\_result\.data\.\*\.package\_spec\.expire\_seconds | numeric | 
action\_result\.data\.\*\.package\_spec\.hidden\_flag | boolean | 
action\_result\.data\.\*\.package\_spec\.id | numeric | 
action\_result\.data\.\*\.package\_spec\.last\_modified\_by | string | 
action\_result\.data\.\*\.package\_spec\.last\_update | string | 
action\_result\.data\.\*\.package\_spec\.mod\_user\.display\_name | string | 
action\_result\.data\.\*\.package\_spec\.mod\_user\.domain | string |  `domain` 
action\_result\.data\.\*\.package\_spec\.mod\_user\.id | numeric | 
action\_result\.data\.\*\.package\_spec\.mod\_user\.name | string | 
action\_result\.data\.\*\.package\_spec\.modification\_time | string | 
action\_result\.data\.\*\.package\_spec\.name | string | 
action\_result\.data\.\*\.package\_spec\.process\_group\_flag | boolean | 
action\_result\.data\.\*\.package\_spec\.skip\_lock\_flag | boolean | 
action\_result\.data\.\*\.package\_spec\.source\_hash | string |  `sha256` 
action\_result\.data\.\*\.package\_spec\.source\_hash\_changed\_flag | boolean | 
action\_result\.data\.\*\.package\_spec\.source\_id | numeric | 
action\_result\.data\.\*\.package\_spec\.verify\_expire\_seconds | numeric | 
action\_result\.data\.\*\.package\_spec\.verify\_group\.id | numeric | 
action\_result\.data\.\*\.package\_spec\.verify\_group\_id | numeric | 
action\_result\.data\.\*\.policy\_flag | boolean | 
action\_result\.data\.\*\.public\_flag | boolean | 
action\_result\.data\.\*\.start\_now\_flag | boolean | 
action\_result\.data\.\*\.start\_time | string | 
action\_result\.data\.\*\.status | numeric | 
action\_result\.data\.\*\.target\_group\.id | numeric | 
action\_result\.data\.\*\.user\.id | numeric | 
action\_result\.data\.\*\.user\.name | string | 
action\_result\.data\.\*\.user\_start\_time | string | 
action\_result\.status | string | 
action\_result\.message | string | 
action\_result\.summary | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'execute action'
Execute an action on the Tanium server

Type: **generic**  
Read only: **False**

<li>See top\-level app documentation for example parameters\.</li><li>If a parameterized package is used for executing an action all the parameters must be provided with correct and unique keys\. If any key is repeated then the value of that key will be overwritten\.</li><li>If the <b>issue\_seconds</b> parameter is provided, then the action will respawn after a time interval provided in the <b>issue\_seconds</b> parameter\.</li>

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**action\_name** |  required  | Creates a name for the action executed | string | 
**action\_group** |  required  | Group of the action | string | 
**package\_name** |  required  | Name of the Tanium package to be executed | string | 
**package\_parameters** |  optional  | Parameter inputs of the corresponding package\. Provide JSON format \(i\.e\. \{"$1"\: "Standard\_Collection", "$2"\: "SCP"\}\) | string | 
**group\_name** |  optional  | The Tanium Computer Group name on which the action will be executed\. If left blank, will execute on all registered IP addresses/hostnames in your Tanium instance | string |  `taniumrest group definition` 
**distribute\_seconds** |  optional  | The number of seconds over which to deploy the action | numeric | 
**issue\_seconds** |  optional  | The number of seconds to reissue an action from the saved action | numeric | 
**expire\_seconds** |  required  | The duration from the start time before the action expires | numeric | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.parameter\.action\_group | string | 
action\_result\.parameter\.action\_name | string | 
action\_result\.parameter\.distribute\_seconds | numeric | 
action\_result\.parameter\.expire\_seconds | numeric | 
action\_result\.parameter\.group\_name | string |  `taniumrest group definition` 
action\_result\.parameter\.issue\_seconds | numeric | 
action\_result\.parameter\.package\_name | string | 
action\_result\.parameter\.package\_parameters | string | 
action\_result\.data\.\*\.action\_group\_id | numeric | 
action\_result\.data\.\*\.approved\_flag | boolean | 
action\_result\.data\.\*\.approver\.id | numeric | 
action\_result\.data\.\*\.approver\.name | string | 
action\_result\.data\.\*\.comment | string | 
action\_result\.data\.\*\.creation\_time | string | 
action\_result\.data\.\*\.distribute\_seconds | numeric | 
action\_result\.data\.\*\.end\_time | string | 
action\_result\.data\.\*\.expire\_seconds | numeric | 
action\_result\.data\.\*\.id | numeric |  `taniumrest question id` 
action\_result\.data\.\*\.issue\_count | numeric | 
action\_result\.data\.\*\.issue\_seconds | numeric | 
action\_result\.data\.\*\.last\_action\.id | numeric | 
action\_result\.data\.\*\.last\_action\.start\_time | string | 
action\_result\.data\.\*\.last\_action\.target\_group\.id | numeric | 
action\_result\.data\.\*\.last\_start\_time | string | 
action\_result\.data\.\*\.name | string | 
action\_result\.data\.\*\.next\_start\_time | string | 
action\_result\.data\.\*\.package\_spec\.available\_time | string | 
action\_result\.data\.\*\.package\_spec\.command | string | 
action\_result\.data\.\*\.package\_spec\.command\_timeout | numeric | 
action\_result\.data\.\*\.package\_spec\.content\_set\.id | numeric | 
action\_result\.data\.\*\.package\_spec\.content\_set\.name | string | 
action\_result\.data\.\*\.package\_spec\.creation\_time | string | 
action\_result\.data\.\*\.package\_spec\.deleted\_flag | boolean | 
action\_result\.data\.\*\.package\_spec\.display\_name | string | 
action\_result\.data\.\*\.package\_spec\.expire\_seconds | numeric | 
action\_result\.data\.\*\.package\_spec\.hidden\_flag | boolean | 
action\_result\.data\.\*\.package\_spec\.id | numeric | 
action\_result\.data\.\*\.package\_spec\.last\_modified\_by | string | 
action\_result\.data\.\*\.package\_spec\.last\_update | string | 
action\_result\.data\.\*\.package\_spec\.mod\_user\.display\_name | string | 
action\_result\.data\.\*\.package\_spec\.mod\_user\.domain | string |  `domain` 
action\_result\.data\.\*\.package\_spec\.mod\_user\.id | numeric | 
action\_result\.data\.\*\.package\_spec\.mod\_user\.name | string | 
action\_result\.data\.\*\.package\_spec\.modification\_time | string | 
action\_result\.data\.\*\.package\_spec\.name | string | 
action\_result\.data\.\*\.package\_spec\.parameters\.\*\.key | string | 
action\_result\.data\.\*\.package\_spec\.parameters\.\*\.type | numeric | 
action\_result\.data\.\*\.package\_spec\.parameters\.\*\.value | string | 
action\_result\.data\.\*\.package\_spec\.process\_group\_flag | boolean | 
action\_result\.data\.\*\.package\_spec\.skip\_lock\_flag | boolean | 
action\_result\.data\.\*\.package\_spec\.source\_hash | string |  `sha256` 
action\_result\.data\.\*\.package\_spec\.source\_hash\_changed\_flag | boolean | 
action\_result\.data\.\*\.package\_spec\.source\_id | numeric | 
action\_result\.data\.\*\.package\_spec\.verify\_expire\_seconds | numeric | 
action\_result\.data\.\*\.package\_spec\.verify\_group\.id | numeric | 
action\_result\.data\.\*\.package\_spec\.verify\_group\_id | numeric | 
action\_result\.data\.\*\.policy\_flag | boolean | 
action\_result\.data\.\*\.public\_flag | boolean | 
action\_result\.data\.\*\.start\_now\_flag | boolean | 
action\_result\.data\.\*\.start\_time | string | 
action\_result\.data\.\*\.status | numeric | 
action\_result\.data\.\*\.target\_group\.id | numeric | 
action\_result\.data\.\*\.user\.id | numeric | 
action\_result\.data\.\*\.user\.name | string | 
action\_result\.data\.\*\.user\_start\_time | string | 
action\_result\.status | string | 
action\_result\.message | string | 
action\_result\.summary | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'run query'
Run a search query on the devices registered on the Tanium server

Type: **investigate**  
Read only: **True**

See top\-level app documentation for example parameters\. For manual questions only, the action waits for <b>timeout\_seconds</b> provided by the user in intervals of 5 seconds to fetch the results\. The action is a success as soon as the results are retrieved or else it will timeout and fail\. As pagination is not implemented, the result\(s\) of the action will be the result\(s\) that are fetched in a single API call\.

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**query\_text** |  required  | Query to run \(in Tanium Question Syntax\) | string |  `taniumrest question text` 
**group\_name** |  optional  | The Tanium Computer Group name on which the query will be executed \(manual query only\) | string | 
**is\_saved\_question** |  optional  | Check this box if the query text parameter refers to a 'Saved Question' on your Tanium | boolean | 
**timeout\_seconds** |  required  | The number of seconds before the question expires \(manual query only\) | numeric | 
**wait\_for\_results\_processing** |  optional  | Flag to wait for endpoint to return full results | boolean | 
**return\_when\_n\_results\_available** |  optional  | Return results as soon as 'n' answers are available | numeric | 
**wait\_for\_n\_results\_available** |  optional  | Wait until 'n' results are present, even if hit the percent complete threshold | numeric | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.parameter\.group\_name | string | 
action\_result\.parameter\.is\_saved\_question | boolean | 
action\_result\.parameter\.query\_text | string |  `taniumrest question text` 
action\_result\.parameter\.timeout\_seconds | numeric | 
action\_result\.parameter\.wait\_for\_results\_processing | boolean | 
action\_result\.parameter\.return\_when\_n\_results\_available | numeric | 
action\_result\.parameter\.wait\_for\_n\_results\_available | numeric | 
action\_result\.data\.\*\.data\.max\_available\_age | string | 
action\_result\.data\.\*\.data\.now | string | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.age | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.archived\_question\_id | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.cache\_id | string | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.columns\.\*\.hash | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.columns\.\*\.name | string | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.columns\.\*\.type | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.error\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.estimated\_total | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.expiration | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.expire\_seconds | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.filtered\_row\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.filtered\_row\_count\_machines | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.id | numeric |  `taniumrest question id` 
action\_result\.data\.\*\.data\.result\_sets\.\*\.issue\_seconds | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.item\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.mr\_passed | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.mr\_tested | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.no\_results\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.passed | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.question\_id | numeric |  `taniumrest question id` 
action\_result\.data\.\*\.data\.result\_sets\.\*\.report\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.row\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.row\_count\_machines | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.rows\.\*\.cid | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.rows\.\*\.data\.\*\.text | string | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.rows\.\*\.id | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.saved\_question\_id | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.seconds\_since\_issued | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.select\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.tested | numeric | 
action\_result\.status | string | 
action\_result\.message | string | 
action\_result\.summary\.number\_of\_rows | numeric | 
action\_result\.summary\.timeout\_seconds | numeric | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'get question results'
Return the results for an already asked question

Type: **investigate**  
Read only: **True**

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**question\_id** |  required  | The ID of the question | numeric |  `taniumrest question id` 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.parameter\.question\_id | numeric |  `taniumrest question id` 
action\_result\.data\.\*\.data\.max\_available\_age | string | 
action\_result\.data\.\*\.data\.now | string | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.age | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.archived\_question\_id | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.cache\_id | string | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.columns\.\*\.hash | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.columns\.\*\.name | string | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.columns\.\*\.type | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.error\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.estimated\_total | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.expiration | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.expire\_seconds | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.filtered\_row\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.filtered\_row\_count\_machines | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.id | numeric |  `taniumrest question id` 
action\_result\.data\.\*\.data\.result\_sets\.\*\.issue\_seconds | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.item\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.mr\_passed | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.mr\_tested | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.no\_results\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.passed | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.question\_id | numeric |  `taniumrest question id` 
action\_result\.data\.\*\.data\.result\_sets\.\*\.report\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.row\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.row\_count\_machines | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.rows\.\*\.cid | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.rows\.\*\.data\.\*\.text | string | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.rows\.\*\.id | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.saved\_question\_id | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.seconds\_since\_issued | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.select\_count | numeric | 
action\_result\.data\.\*\.data\.result\_sets\.\*\.tested | numeric | 
action\_result\.status | string | 
action\_result\.message | string | 
action\_result\.summary\.number\_of\_rows | numeric | 
action\_result\.summary\.timeout\_seconds | numeric | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric | 