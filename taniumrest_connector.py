# File: taniumrest_connector.py
#
# Copyright (c) 2019-2022 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions
# and limitations under the License.
#
#

import ast
import json
import os
import sys
from time import sleep

import phantom.app as phantom
import requests
from bs4 import BeautifulSoup, UnicodeDammit
from phantom.action_result import ActionResult
from phantom.base_connector import BaseConnector

from taniumrest_consts import *


class RetVal(tuple):
    def __new__(cls, val1, val2=None):
        return tuple.__new__(RetVal, (val1, val2))


class TaniumRestConnector(BaseConnector):

    def __init__(self):

        # Call the BaseConnectors init first
        super(TaniumRestConnector, self).__init__()

        self._state = None
        self._base_url = None
        self._api_token = None
        self._username = None
        self._password = None
        self._verify = None
        self._session_id = None
        self._session_key = None
        self._percentage = None
        self._python_version = None

    def _handle_py_ver_compat_for_input_str(self, input_str):
        """
        This method returns the encoded|original string based on the Python version.

        :param input_str: Input string to be processed
        :return: input_str (Processed input string based on following logic 'input_str - Python 3; encoded input_str - Python 2')
        """

        try:
            if input_str and self._python_version == 2:
                input_str = UnicodeDammit(input_str).unicode_markup.encode('utf-8')
        except Exception:
            self.debug_print("Error occurred while handling python 2to3 compatibility for the input string")

        return input_str

    def _get_error_message_from_exception(self, e):
        """ This function is used to get appropriate error message from the exception.
        :param e: Exception object
        :return: error message
        """

        error_code = TANIUMREST_ERR_CODE_MSG
        error_msg = TANIUMREST_ERR_MSG_UNAVAILABLE
        try:
            if e.args:
                if len(e.args) > 1:
                    error_code = e.args[0]
                    error_msg = e.args[1]
                elif len(e.args) == 1:
                    error_code = TANIUMREST_ERR_CODE_MSG
                    error_msg = e.args[0]
        except Exception:
            self.debug_print("Error occurred while retrieving exception information")

        try:
            error_msg = self._handle_py_ver_compat_for_input_str(error_msg)
        except TypeError:
            error_msg = TANIUMREST_TYPE_ERR_MSG
        except Exception:
            error_msg = TANIUMREST_ERR_MSG_UNAVAILABLE

        return error_code, error_msg

    def _validate_integer(self, action_result, parameter, key, allow_zero=False):
        """ This function is a validation function to check if the provided input parameter value
        is a non-zero positive integer and returns the integer value of the parameter itself.
        :param action_result: Action result object
        :param parameter: input parameter
        :param key: input parameter message key
        :param allow_zero: whether to allow zero as a valid integer or not
        :return: integer value of the parameter
        """
        if parameter is not None:
            try:
                if not float(parameter).is_integer():
                    return action_result.set_status(phantom.APP_ERROR, TANIUMREST_INVALID_INT_ERR_MSG.format(key)), None

                parameter = int(parameter)
            except Exception:
                return action_result.set_status(phantom.APP_ERROR, TANIUMREST_INVALID_INT_ERR_MSG.format(key)), None

            if parameter < 0:
                return action_result.set_status(phantom.APP_ERROR, TANIUMREST_INVALID_NON_NEG_INT_ERR_MSG.format(key)), None
            if not allow_zero and parameter == 0:
                return action_result.set_status(phantom.APP_ERROR, TANIUMREST_INVALID_NON_NEG_NON_ZERO_ERR_MSG.format(key)), None

        return phantom.APP_SUCCESS, parameter

    def _process_empty_response(self, response, action_result):

        if response.status_code == 200:
            return RetVal(phantom.APP_SUCCESS, {})

        return RetVal(action_result.set_status(
            phantom.APP_ERROR,
            "Status Code: {}. Empty response and no information in the header".format(response.status_code)), None)

    def _process_content_response(self, response, action_result):
        """ Process plain content from an API call. Can be used for downloading files.

        Args:
            response (Response): response from API request
            action_result (ActionResult): object of ActionResult class

        Returns:
            RetVal:
                * ActionResult: status success/failure
                * Response or None:
        """

        if 200 <= response.status_code < 400:
            return RetVal(phantom.APP_SUCCESS, response)

        message = 'Error from server. Status code: {0}'.format(response.status_code)

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _process_html_response(self, response, action_result):

        # An html response, treat it like an error
        status_code = response.status_code

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove the script, style, footer and navigation part from the HTML message
            for element in soup(["script", "style", "footer", "nav"]):
                element.extract()
            error_text = soup.text
            split_lines = error_text.split('\n')
            split_lines = [x.strip() for x in split_lines if x.strip()]
            error_text = '\n'.join(split_lines)
        except Exception:
            error_text = "Cannot parse error details"

        message = "Status Code: {0}. Data from server:\n{1}\n".format(
                status_code,
                self._handle_py_ver_compat_for_input_str(error_text))

        message = message.replace('{', '{{').replace('}', '}}')

        if len(message) > 500:
            message = "Error while connecting to the server: message len > 500"

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _process_json_response(self, r, action_result):

        # Try a json parse
        try:
            resp_json = r.json()
        except Exception as e:
            error_code, error_msg = self._get_error_message_from_exception(e)
            return RetVal(action_result.set_status(
                phantom.APP_ERROR,
                "Unable to parse JSON response. Error Code: {0} Error Message: {1}".format(error_code, error_msg)), None)

        # Please specify the status codes here
        if 200 <= r.status_code < 399:
            return RetVal(phantom.APP_SUCCESS, resp_json)

        # You should process the error returned in the json
        try:
            if resp_json.get('text'):
                message = "Error from server. Status Code: {0} Data from \
                    server: {1}".format(r.status_code, self._handle_py_ver_compat_for_input_str(resp_json.get('text')))
            else:
                message = "Error from server. Status Code: {0} Data from server: {1}".format(
                        r.status_code, self._handle_py_ver_compat_for_input_str(r.text.replace('{', '{{').replace('}', '}}')))
            if r.status_code == 404:
                permission_error = "\nThis error usually means the account you are using to interface to Tanium " \
                    "does not have sufficient permissions to perform this action. See Tanium's documentation " \
                    "for more information on how to change your permissions."
                message = "{}{}".format(message, permission_error)
        except Exception:
            message = "Error from server. Status Code: {0}. Please provide valid input".format(r.status_code)

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _process_response(self, r, action_result):

        # store the r_text in debug data, it will get dumped in the logs if the action fails
        if hasattr(action_result, 'add_debug_data'):
            action_result.add_debug_data({'r_status_code': r.status_code})
            action_result.add_debug_data({'r_text': r.text})
            action_result.add_debug_data({'r_headers': r.headers})

        # Process each 'Content-Type' of response separately

        # Process a json response
        if 'json' in r.headers.get('Content-Type', ''):
            return self._process_json_response(r, action_result)

        # Process an HTML response, Do this no matter what the api talks.
        # There is a high chance of a PROXY in between phantom and the rest of
        # world, in case of errors, PROXY's return HTML, this function parses
        # the error and adds it to the action_result.
        if 'html' in r.headers.get('Content-Type', ''):
            return self._process_html_response(r, action_result)

        # it's not content-type that is to be parsed, handle an empty response
        if not r.text:
            return self._process_empty_response(r, action_result)

        # everything else is actually an error at this point
        message = "Can't process response from server. Status Code: {0} Data from server: {1}".format(
                r.status_code, self._handle_py_ver_compat_for_input_str(r.text.replace('{', '{{').replace('}', '}}')))

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _make_rest_call(self, endpoint, action_result, verify=True, headers=None,
                        params=None, data=None, json=None, method="get"):
        """ Function that makes the REST call to the app.

        :param endpoint: REST endpoint that needs to appended to the service address
        :param action_result: object of ActionResult class
        :param headers: request headers
        :param params: request parameters
        :param data: request body
        :param json: JSON object
        :param method: GET/POST/PUT/DELETE/PATCH (Default will be GET)
        :param verify: verify server certificate (Default True)
        :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message),
        response obtained by making an API call
        """
        resp_json = None

        try:
            request_func = getattr(requests, method)
        except AttributeError:
            return RetVal(action_result.set_status(phantom.APP_ERROR, "Invalid method: {0}".format(method)), resp_json)

        try:
            r = request_func(endpoint, json=json, data=data, headers=headers, verify=verify, params=params)
        except requests.exceptions.InvalidURL:
            error_message = "Error connecting to server. Invalid URL: %s" % endpoint
            return RetVal(action_result.set_status(phantom.APP_ERROR, error_message), resp_json)
        except requests.exceptions.InvalidSchema:
            error_message = "Error connecting to server. No connection adapters were found for %s" % endpoint
            return RetVal(action_result.set_status(phantom.APP_ERROR, error_message), resp_json)
        except requests.exceptions.ConnectionError:
            error_message = 'Error connecting to server. Connection Refused from the Server for %s' % endpoint
            return RetVal(action_result.set_status(phantom.APP_ERROR, error_message), resp_json)
        except Exception as e:
            error_code, error_msg = self._get_error_message_from_exception(e)
            return RetVal(action_result.set_status(
                phantom.APP_ERROR,
                "Error occurred while making the REST call to the Tanium server. Error Code: {0}. Error Message: {1}"
                .format(error_code, error_msg)), None)

        return self._process_response(r, action_result)

    def _make_rest_call_helper(self, action_result, endpoint, verify=True, headers=None,
                               params=None, data=None, json=None, method="get"):
        """ Function that helps setting REST call to the app.

        :param endpoint: REST endpoint that needs to appended to the service address
        :param action_result: object of ActionResult class
        :param headers: request headers
        :param params: request parameters
        :param data: request body
        :param json: JSON object
        :param method: GET/POST/PUT/DELETE/PATCH (Default will be GET)
        :param verify: verify server certificate (Default True)
        :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message),
        response obtained by making an API call
        """

        url = "{0}{1}".format(self._base_url, endpoint)
        if headers is None:
            headers = {}

        if not self._session_id:
            ret_val = self._get_token(action_result)
            if phantom.is_fail(ret_val):
                return action_result.get_status(), None

        headers.update({
                'session': str(self._session_id),
                'Content-Type': 'application/json'
            })

        ret_val, resp_json = self._make_rest_call(
            url, action_result, verify=verify, headers=headers, params=params, data=data, json=json, method=method)

        # If token is expired, generate a new token
        msg = action_result.get_message()

        if msg and ("403" in msg or "401" in msg):
            self.debug_print("Refreshing Tanium API and re-trying request to [{0}] because API "
                             "token was expired or invalid with error code [{1}]".format(url, msg))
            ret_val = self._get_token(action_result)

            if phantom.is_fail(ret_val):
                self.debug_print("Attempt to refresh Tanium API session token failed!")
                return action_result.get_status(), None

            headers.update({'session': str(self._session_id), 'Content-Type': 'application/json'})

            ret_val, resp_json = self._make_rest_call(
                url, action_result, verify=verify, headers=headers, params=params, data=data, json=json, method=method)
        elif msg and ("404" in msg and "result_data/question" in endpoint):
            # Issue seen in Tanium 7.3.314.4103. Sometimes it returns a 404 for a sensor and says that the sensor
            # doesn't exist even though it does. A short sleep and resubmit fixes the issue
            self.debug_print("Encountered Tanium `REST Object Not Found Exception: "
                             "SensorNotFound: The requested sensor was not found` error")
            sleep(5)
            ret_val, resp_json = self._make_rest_call(
                url, action_result, verify=verify, headers=headers, params=params, data=data, json=json, method=method)

        if phantom.is_fail(ret_val):
            self.debug_print("REST API Call Failure! Failed call to Tanium API endpoint {0} with error code {1}".format(url, msg))
            return action_result.get_status(), None

        return phantom.APP_SUCCESS, resp_json

    def _get_token(self, action_result, from_action=False):
        """ If an API token is not already provided, this function is used to get a token via REST call.

        :param action_result: Object of action result
        :param from_action: Boolean object of from_action
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """

        data = {
            'username': self._username,
            'password': self._password
        }
        headers = {
            'Content-Type': 'application/json'
        }

        ret_val, resp_json = self._make_rest_call(
            "{}{}".format(self._base_url, TANIUMREST_SESSION_URL), action_result,
            verify=self._verify, headers=headers, json=data, method='post')

        if phantom.is_fail(ret_val):
            self.debug_print("Failed to fetch a session token from Tanium API!")
            self.save_progress("Failed to fetch a session token from Tanium API!")
            self._state['session_id'] = None
            self._session_id = None
            self.save_state(self._state)
            return action_result.get_status()

        self._state['session_id'] = resp_json.get('data', {}).get('session')
        self._session_id = resp_json.get('data', {}).get('session')
        self.save_state(self._state)

        return phantom.APP_SUCCESS

    def _get_filename_from_tanium(self, action_result, file_id):

        filename = None

        endpoint = '/plugin/products/trace/filedownloads'
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('List Files Failed')
            return RetVal(action_result.get_status(), None)

        for f in response:
            if f.get('id') == file_id:
                filename = f.get('path', '').split('\\')[-1]
                break

        return RetVal(phantom.APP_SUCCESS, filename)

    def _save_temp_file(self, content):
        """

        Args:
            content:

        Returns:

        """

        if hasattr(Vault, 'get_vault_tmp_dir'):
            temp_dir = Vault.get_vault_tmp_dir()
        else:
            temp_dir = '/opt/phantom/vault/tmp'

        temp_dir = '{}/{}'.format(temp_dir, uuid.uuid4())
        os.makedirs(temp_dir)

        file_obj = tempfile.NamedTemporaryFile(prefix='taniumthreatresponse_',
                                               dir=temp_dir,
                                               delete=False)
        file_obj.close()

        with open(file_obj.name, 'wb') as f:
            f.write(content)

        return file_obj.name

    def _list_connections(self, action_result):
        """ Return a list of current connections.

        Args:
            action_result (ActionResult): object of ActionResult class

        Returns:
            RetVal:
                bool: Success/ Failure
                list: Current connections in Tanium Threat Response

        """

        endpoint = '/plugin/products/trace/conns'
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            message = self._handle_py_ver_compat_for_input_str(action_result.get_message())
            return RetVal(action_result.set_status(phantom.APP_ERROR, 'Unable to list connections{}'.format('. Error message: {}'.format(message) if message else "")), None)

        return RetVal(phantom.APP_SUCCESS, response)

    def _is_connection_active(self, action_result, conn_id):
        """ Check to see if connection exists and is active.

        Args:
            action_result (ActionResult): object of ActionResult class
            conn_id (str): Connection ID to check if it is active

        Returns:
            bool: Success/ Failure
        """

        ret_val, response = self._list_connections(action_result)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        for connection in response:
            if conn_id == connection.get('name', ''):
                state = connection.get('info', {}).get('state', '')
                if state == 'active':
                    return phantom.APP_SUCCESS
                elif not state:
                    message = 'Connection not active. Error occurred while fetching the state of the connection'
                    return action_result.set_status(phantom.APP_ERROR, message)
                else:
                    message = 'Connection not active. Current state: {}'.format(state)
                    return action_result.set_status(phantom.APP_ERROR, message)

        message = 'Could not find connection'
        return action_result.set_status(phantom.APP_ERROR, message)

    def _handle_test_connectivity(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))

        self.save_progress("Connecting to endpoint")

        if not self._api_token:
            ret_val = self._get_token(action_result)
            if phantom.is_fail(ret_val):
                self.save_progress("Test Connectivity Failed")
                return action_result.get_status()

        # make rest call
        ret_val, response = self._make_rest_call_helper(
            action_result, TANIUMREST_GET_SAVED_QUESTIONS, verify=self._verify, params=None, headers=None)

        if phantom.is_fail(ret_val):
            self.save_progress("Test Connectivity Failed")
            return action_result.get_status()

        self.save_progress("Test Connectivity Passed")
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_list_computers(self, param):
        """ Get a list of computers that match name passed in param.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        # name is a required parameter, but it can be blank.
        params = {'name': self._handle_py_ver_compat_for_input_str(param.get('name', ''))}
        endpoint = '/plugin/products/trace/computers/'

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, params=params)
        if phantom.is_fail(ret_val):
            self.save_progress('List Computers Failed')
            return action_result.get_status()

        if not response:
            return action_result.set_status(phantom.APP_SUCCESS, 'No results found')

        summary = action_result.update_summary({})
        summary['total_results'] = len(response)

        for r in response:
            action_result.add_data({'name': r})

        self.save_progress('List computers successful')
        message = 'Retrieved list of computers'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_initialize_computers_list(self, param):
        """ Initialize the endpoints

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        endpoint = '/plugin/products/trace/computers/initialize'
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, method='post')

        if phantom.is_fail(ret_val):
            self.save_progress('Initialize computers failed')
            return action_result.get_status()

        self.save_progress('Initialize computers successful')
        message = 'Requested an initialize computer action'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_list_connections(self, param):
        """ List the current connections

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        ret_val, response = self._list_connections(action_result)

        if phantom.is_fail(ret_val):
            self.save_progress('List connections failed')
            return action_result.get_status()

        summary = action_result.update_summary({})
        try:
            for state in [x['info']['state'] for x in response if 'state' in x['info']]:
                summary['{}_connections'.format(state)] = len([x for x in response if 'state' in x['info'] and x['info']['state'] == state])
        except Exception as e:
            error_code, error_msg = self._get_error_message_from_exception(e)
            return RetVal(action_result.set_status(
                phantom.APP_ERROR,
                "Unable to parse JSON response. Error Code: {0} Error Message: {1}".format(error_code, error_msg)), None)

        summary['total_connections'] = len(response)
        for r in response:
            action_result.add_data(r)

        self.save_progress('List connections successful')
        message = 'Number of active connections found: {}'.format(summary.get('active_connections', 0))
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_create_connection(self, param):
        """ Create connection with an endpoint.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        ret_val, conntimeout = self._validate_integer(action_result, param.get('conntimeout'), TANIUMREST_CONNTIMEOUT_KEY, False)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        dsttype = self._handle_py_ver_compat_for_input_str(param.get('dsttype'))
        if dsttype not in TANIUMREST_DSTTYPE_VALUE_LIST:
            return action_result.set_status(phantom.APP_ERROR, "Please provide valid input from {} in 'dsttype' action parameter".format(TANIUMREST_DSTTYPE_VALUE_LIST))

        data = {'dst': self._handle_py_ver_compat_for_input_str(param.get('dst')),
                'dstType': dsttype,
                'remote': param.get('remote', True)}

        if conntimeout:
            data.update({'connTimeout': conntimeout})

        endpoint = '/plugin/products/trace/conns'
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, json=data, method='post')

        if phantom.is_fail(ret_val):
            self.save_progress('Create connection failed')
            return action_result.get_status()

        self.save_progress('Create connection successful')
        message = 'Create connection requested'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_get_connection(self, param):
        """ Get connection information.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        cid = self._handle_py_ver_compat_for_input_str(param.get('connection_id'))

        endpoint = '/plugin/products/trace/conns/{}'.format(cid)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('Get connection failed')
            return action_result.get_status()

        action_result.add_data(response)

        self.save_progress('Get connection successful')
        message = 'Connection information found'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_delete_connection(self, param):
        """ Deletes specified connection.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        cid = self._handle_py_ver_compat_for_input_str(param.get('connection_id'))

        endpoint = '/plugin/products/trace/conns/{}'.format(cid)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, method='delete')

        if phantom.is_fail(ret_val):
            self.save_progress('Delete connection failed')
            return action_result.get_status()

        self.save_progress('Delete connection successful')
        message = 'Delete connection requested'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_list_snapshots(self, param):
        """ List existing snapshots.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        endpoint = '/plugin/products/trace/locals'
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('List snapshots failed')
            return action_result.get_status()

        for host, names in response.iteritems():
            for name in names:
                each_snapshot = dict()
                each_snapshot['host'] = host
                each_snapshot['name'] = name
                action_result.add_data(each_snapshot)

        summary = action_result.update_summary({})
        summary['total_snapshots'] = action_result.get_data_size()

        self.save_progress('List snapshots successful')
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_create_snapshot(self, param):
        """ Create new snapshot. Requires a connection to already be setup.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """

        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        cid = self._handle_py_ver_compat_for_input_str(param['connection_id'])

        if not self._is_connection_active(action_result, cid):
            self.save_progress('Inactive or non-existent connection')
            return action_result.get_status()

        endpoint = '/plugin/products/trace/conns/{}/snapshots'.format(cid)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, method='post')

        if phantom.is_fail(ret_val):
            self.save_progress('Create snapshot failed')
            return action_result.get_status()

        self.save_progress('Create snapshot successful')
        message = 'Create snapshot requested'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_delete_snapshot(self, param):
        """ Delete existing snapshot.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        host = self._handle_py_ver_compat_for_input_str(param['host'])
        filename = self._handle_py_ver_compat_for_input_str(param['filename'])

        endpoint = '/plugin/products/trace/locals/{}/{}'.format(host, filename)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, method='delete')

        if phantom.is_fail(ret_val):
            self.save_progress('Delete snapshot failed')
            return action_result.get_status()

        self.save_progress('Delete snapshot successful')
        message = 'Delete snapshot requested'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_list_local_snapshots(self, param):
        """ List all of the local snapshots and their file sizes.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        endpoint = '/plugin/products/trace/snapshots'
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('List local snapshots failed')
            return action_result.get_status()

        for name, entry in response.iteritems():
            for key, value in entry.iteritems():
                each_snapshot = dict()
                each_snapshot.update(value)
                each_snapshot['snapshot'] = key
                each_snapshot['connection_id'] = name
                action_result.add_data(each_snapshot)

        summary = action_result.update_summary({})
        summary['total_snapshots'] = action_result.get_data_size()

        self.save_progress('List local snapshots successful')
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_get_local_snapshot(self, param):
        """ Download a local snapshot to the Vault.

        TODO: Action is DISABLED until "upload local snapshot" can work.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        directory = UnicodeDammit(param['directory'].strip()).unicode_markup.encode('utf-8')
        filename = UnicodeDammit(param['filename'].strip()).unicode_markup.encode('utf-8')
        endpoint = '/plugin/products/trace/locals/{}/{}'.format(directory, filename)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('Get local snapshot failed')
            return action_result.get_status()

        metadata = {
            'size': len(response.content),
            'contains': ['threatresponse snapshot'],
            'action': self.get_action_name(),
            'app_run_id': self.get_app_run_id()
        }

        file_name = '{}_{}'.format(directory, filename)

        # Save file
        self.send_progress('Saving file to disk')
        try:
            temp_name = self._save_temp_file(response.content)
        except Exception as e:
            self.debug_print('Error creating file')
            error_code, error_msg = self._get_error_message_from_exception(e)
            return RetVal(action_result.set_status(
                phantom.APP_ERROR,
                "Unable to parse JSON response. Error Code: {0} Error Message: {1}".format(error_code, error_msg)), None)


        vault = Vault.add_attachment(temp_name, self.get_container_id(), file_name=file_name, metadata=metadata)
        if filename:
            vault['file_name'] = file_name

        action_result.add_data(vault)

        self.save_progress('Get local snapshot successful')
        message = 'Downloaded snapshot to vault'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_upload_local_snapshot(self, param):
        """ Upload local snapshot.

        TODO: DISABLED until we can get the API to work

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        vault_id = param['vault_id']
        file_path = Vault.get_file_path(vault_id)
        data = open(file_path, 'rb').read()

        endpoint = '/plugin/products/trace/locals'
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, data=data, method='post')

        if phantom.is_fail(ret_val):
            self.save_progress('Upload local snapshot failed')
            return action_result.get_status()

        self.save_progress('Upload local snapshot successful')
        message = 'Uploaded snapshot from vault'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_delete_local_snapshot(self, param):
        """ Delete a local snapshot.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        cid = self._handle_py_ver_compat_for_input_str(param.get('connection_id'))
        db = self._handle_py_ver_compat_for_input_str(param.get('snapshot'))

        if not self._is_connection_active(action_result, cid):
            self.save_progress('Inactive or non-existent connection')
            return action_result.get_status()

        endpoint = '/plugin/products/trace/conns/{}/snapshots/{}'.format(cid, db)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, method='delete')

        if phantom.is_fail(ret_val):
            self.save_progress('Delete local snapshot failed')
            return action_result.get_status()

        self.save_progress('Delete local snapshot successful')
        message = 'Delete local snapshot requested'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_get_process(self, param):
        """ Get process information from an existing connection.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        cid = self._handle_py_ver_compat_for_input_str(param['connection_id'])
        ret_val, ptid = self._validate_integer(action_result, param.get('process_table_id'), TANIUMREST_PROCESS_TABLE_ID_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        if not self._is_connection_active(action_result, cid):
            self.save_progress('Inactive or non-existent connection')
            return action_result.get_status()

        endpoint = '/plugin/products/trace/conns/{0}/processes/{1}'.format(cid, ptid)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('Get process failed')
            return action_result.get_status()

        action_result.add_data(response)

        self.save_progress('Get process successful')
        message = 'Process information retrieved'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_get_process_timeline(self, param):
        """ Get process timeline from an existing connection.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        cid = self._handle_py_ver_compat_for_input_str(param['connection_id'])
        ret_val, ptid = self._validate_integer(action_result, param.get('process_table_id'), TANIUMREST_PROCESS_TABLE_ID_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        if not self._is_connection_active(action_result, cid):
            self.save_progress('Inactive or non-existent connection')
            return action_result.get_status()

        endpoint = '/plugin/products/trace/conns/{0}/eprocesstimelines/{1}'.format(cid, ptid)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('Get Process Timeline Failed')
            return action_result.get_status()

        # Process response
        out = []
        for event_type in response:
            for date, l in event_type.get('details', {}).iteritems():
                for event in l:
                    out.append({
                        'type': event_type.get('name'),
                        'date': date,
                        'isodate': '{}Z'.format(datetime.datetime.utcfromtimestamp(int(date) / 1000).isoformat()),
                        'event': event
                    })

        # Sort and add to action result
        sorted_out = sorted(out, key=lambda x: x['date'])
        for each_out in sorted_out:
            action_result.add_data(each_out)

        self.save_progress('Get Process Timeline Successful')
        message = 'Process timeline retrieved'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_get_process_tree(self, param):
        """ Get process tree for a process from an existing connection.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        cid = self._handle_py_ver_compat_for_input_str(param['connection_id'])
        ret_val, ptid = self._validate_integer(action_result, param.get('process_table_id'), TANIUMREST_PROCESS_TABLE_ID_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        if not self._is_connection_active(action_result, cid):
            self.save_progress('Inactive or non-existent connection')
            return action_result.get_status()

        endpoint = '/plugin/products/trace/conns/{0}/processtrees/{1}'.format(cid, ptid)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('Get process tree Failed')
            return action_result.get_status()

        if response:
            action_result.add_data(response[0])
        else:
            return action_result.set_status(phantom.APP_SUCCESS, 'No process tree found')

        self.save_progress('Get process tree Successful')
        message = 'Process tree retrieved'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_get_parent_process_tree(self, param):
        """ Get parent process tree for a process from an existing connection.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        cid = self._handle_py_ver_compat_for_input_str(param['connection_id'])
        ret_val, ptid = self._validate_integer(action_result, param.get('process_table_id'), TANIUMREST_PROCESS_TABLE_ID_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        if not self._is_connection_active(action_result, cid):
            self.save_progress('Inactive or non-existent connection')
            return action_result.get_status()

        endpoint = '/plugin/products/trace/conns/{0}/parentprocesstrees/{1}'.format(cid, ptid)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('Get parent process tree Failed')
            return action_result.get_status()

        if response:
            action_result.add_data(response[0])
        else:
            return action_result.set_status(phantom.APP_SUCCESS, 'No parent process tree found')

        self.save_progress('Get Parent process tree Successful')
        message = 'Parent process tree retrieved'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_get_children_process_tree(self, param):
        """ Get children process tree for a process from an existing connection.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        cid = self._handle_py_ver_compat_for_input_str(param['connection_id'])
        ret_val, ptid = self._validate_integer(action_result, param.get('process_table_id'), TANIUMREST_PROCESS_TABLE_ID_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        if not self._is_connection_active(action_result, cid):
            self.save_progress('Inactive or non-existent connection')
            return action_result.get_status()

        endpoint = '/plugin/products/trace/conns/{0}/processtrees/{1}/children'.format(cid, ptid)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('Get children process tree Failed')
            return action_result.get_status()

        if response:
            action_result.add_data(response[0])
        else:
            return action_result.set_status(phantom.APP_SUCCESS, 'No children process tree found')

        self.save_progress('Get children process tree Successful')
        return action_result.set_status(phantom.APP_SUCCESS, 'Children process tree retrieved')

    def _handle_get_events(self, param):
        """ Return events and number of events of a certain type where the value exists in one or more
        of the queried fields from an existing connection.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """

        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        event_type = self._handle_py_ver_compat_for_input_str(param['event_type'])
        if event_type not in TANIUMREST_EVENT_TYPE_VALUE_LIST:
            return action_result.set_status(phantom.APP_ERROR, "Please provide valid input from {} in 'event_type' action parameter".format(TANIUMREST_EVENT_TYPE_VALUE_LIST))

        ret_val, limit = self._validate_integer(action_result, param.get('limit'), TANIUMREST_LIMIT_KEY, False)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        ret_val, offset = self._validate_integer(action_result, param.get('offset'), TANIUMREST_OFFSET_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        sort = self._handle_py_ver_compat_for_input_str(param.get('sort'))
        fields = self._handle_py_ver_compat_for_input_str(param.get('fields'))
        operators = self._handle_py_ver_compat_for_input_str(param.get('operators'))
        value = self._handle_py_ver_compat_for_input_str(param.get('value'))
        cid = self._handle_py_ver_compat_for_input_str(param['connection_id'])

        if not self._is_connection_active(action_result, cid):
            self.save_progress('Inactive or non-existent connection')
            return action_result.get_status()

        params = {}

        if fields or value or operators:
            if not (fields and value and operators):
                return action_result.set_status(phantom.APP_ERROR, 'fields, operators, and value need to be filled in to query events. Returning all results')
            else:

                filter_type = self._handle_py_ver_compat_for_input_str(param.get("filter_type", "all"))
                if filter_type and filter_type not in TANIUMREST_FILTER_TYPE_VALUE_LIST:
                    return action_result.set_status(phantom.APP_ERROR, "Please provide valid input from {} in 'filter_type' action parameter".format(TANIUMREST_FILTER_TYPE_VALUE_LIST))

                fields = [field.strip() for field in fields.split(',')]
                fields = list(filter(None, fields))

                value = [val.strip() for val in value.split(',')]
                value = list(filter(None, value))

                operators = [operator.strip() for operator in operators.split(',')]
                operators = list(filter(None, operators))

                if not (len(fields) == len(value) and len(value) == len(operators)):
                    return action_result.set_status(phantom.APP_ERROR, "Length of value, fields , and operators must be equal")

                group_list = []

                for i, _filter in enumerate(fields):
                    params["f{}".format(str(i))] = fields[i]
                    params["o{}".format(str(i))] = operators[i]
                    params["v{}".format(str(i))] = value[i]
                    group_list.append(str(i))

                params["gm1"] = filter_type
                params["g1"] = ",".join(group_list)

        endpoint = '/plugin/products/trace/conns/{0}/{1}/eventsCount'.format(cid, event_type)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, params=params)

        if phantom.is_fail(ret_val):
            self.save_progress('Get Events Count Failed')
            return action_result.get_status()

        action_result.update_summary({'event_count': response})

        if limit:
            params['limit'] = limit
        if offset:
            params['offset'] = offset
        if sort:
            params['sort'] = sort

        endpoint = '/plugin/products/trace/conns/{0}/{1}/events'.format(cid, event_type)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, params=params)

        if phantom.is_fail(ret_val):
            self.save_progress('Get Events Failed')
            return action_result.get_status()

        for event in response:
            action_result.add_data(event)
        action_result.update_summary({'type': event_type})

        self.save_progress('Get Events Successful')
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_get_events_summary(self, param):
        """ Return counts of event types and operations from an existing connection.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """

        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        cid = self._handle_py_ver_compat_for_input_str(param['connection_id'])

        if not self._is_connection_active(action_result, cid):
            self.save_progress('Inactive or non-existent connection')
            return action_result.get_status()

        endpoint = '/plugin/products/trace/conns/{}/eventcounts'.format(cid)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('Events Summary Failed')
            return action_result.get_status()

        if not response:
            response = []

        for r in response:
            action_result.add_data(r)

        # Add a dictionary that is made up of the most important values from data into the summary
        summary = action_result.update_summary({})
        try:
            summary['total_categories'] = len(set([r['category'] for r in response]))
            summary['total_events_operations'] = len(response)
            summary['total_events_count'] = sum([int(r['count']) for r in response])
        except Exception as e:
            error_code, error_msg = self._get_error_message_from_exception(e)
            return RetVal(action_result.set_status(
                phantom.APP_ERROR,
                "Unable to parse JSON response. Error Code: {0} Error Message: {1}".format(error_code, error_msg)), None)

        self.save_progress('Events Summary Successful')
        message = 'Number of categories found: {}'.format(summary.get('total_categories'))
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_list_files(self, param):
        """ Return list of saved files and number of files.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """

        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        endpoint = '/plugin/products/trace/filedownloads'
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('List Files Failed')
            return action_result.get_status()

        if not response:
            return action_result.set_status(phantom.APP_SUCCESS, 'No results found')

        for r in response:
            action_result.add_data(r)

        # Add a dictionary that is made up of the most important values from data into the summary
        summary = action_result.update_summary({})
        summary['file_count'] = len(response)

        self.save_progress('List Files Successful')
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_save_file(self, param):
        """ Save file from remote computer to Tanium Threat Response.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """

        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        cid = self._handle_py_ver_compat_for_input_str(param['connection_id'])

        if not self._is_connection_active(action_result, cid):
            self.save_progress('Inactive or non-existent connection')
            return action_result.get_status()

        data = {
            'connId': cid,
            'path': self._handle_py_ver_compat_for_input_str(param.get('file_path'))
        }

        endpoint = '/plugin/products/trace/filedownloads'
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, json=data, method='post')

        if phantom.is_fail(ret_val):
            self.save_progress('Save File Failed')
            return action_result.get_status()

        self.save_progress('Save File Successful')
        message = 'Save file requested'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_delete_file(self, param):
        """ Delete a downloaded file from Tanium Threat Response.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """

        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))
        ret_val, file_id = self._validate_integer(action_result, param["file_id"], TANIUMREST_FILE_ID_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        endpoint = '/plugin/products/trace/filedownloads/{file_id}'.format(file_id=file_id)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, method='delete')

        if phantom.is_fail(ret_val):
            self.save_progress('Delete File Failed')
            return action_result.get_status()

        self.save_progress('Delete File Successful')
        message = 'Delete file requested'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_get_file(self, param):
        """ Download a file from Tanium Threat Response to the Phantom Vault.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """

        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))
        ret_val, file_id = self._validate_integer(action_result, param["file_id"], TANIUMREST_FILE_ID_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        endpoint = '/plugin/products/trace/filedownloads/{file_id}'.format(file_id=file_id)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            self.save_progress('Get File Failed')
            return action_result.get_status()

        metadata = {
            'size': len(response.content),
            'contains': [],
            'action': self.get_action_name(),
            'app_run_id': self.get_app_run_id()
        }

        # Get file name from Tanium, if it exists
        ret_val, filename = self._get_filename_from_tanium(action_result, file_id)

        # Save file
        self.send_progress('Saving file to disk')
        try:
            temp_name = self._save_temp_file(response.content)
        except Exception as e:
            self.debug_print('Error creating file')
            error_code, error_msg = self._get_error_message_from_exception(e)
            return RetVal(action_result.set_status(
                phantom.APP_ERROR,
                "Unable to parse JSON response. Error Code: {0} Error Message: {1}".format(error_code, error_msg)), None)


        if phantom.is_fail(ret_val) or not filename:
            filename = temp_name.split('/')[-1]

        vault = Vault.add_attachment(temp_name, self.get_container_id(), file_name=filename, metadata=metadata)
        if filename:
            vault['file_name'] = filename

        action_result.add_data(vault)

        self.save_progress('Get File Successful')
        message = 'File downloaded to vault'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_upload_intel_doc(self, param):
        """ Upload intel document to Tanium Threat Response.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        ''' future TODO: file ingestion
        vault_id = param['vault_id']
        file_path = Vault.get_file_path(vault_id)
        data = open(file_path, 'rb').read()
        '''

        headers = {
            'Content-Type': 'application/xml'
        }

        data = self._handle_py_ver_compat_for_input_str(param['intel_doc'])

        endpoint = '/plugin/products/detect3/api/v1/intels'
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, headers=headers, data=data, method='post')

        if phantom.is_fail(ret_val):
            self.save_progress('Upload intel document failed')
            return action_result.get_status()

        action_result.add_data(response)

        self.save_progress('Upload intel document successful')
        message = 'Uploaded intel document to Tanium Threat Response'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_start_quick_scan(self, param):
        """ Scan a computer group for hashes in intel document.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        computer_group_name = self._handle_py_ver_compat_for_input_str(param['computer_group_name'])
        ret_val, intel_doc_id = self._validate_integer(action_result, param.get('intel_doc_id'), TANIUMREST_INTEL_DOC_ID_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()
        endpoint = "{}/{}".format("/api/v2/groups/by-name", computer_group_name)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        response_data = response.get("data")

        if not response_data:
            error_message = "No group exists with name {}. Also, please verify that your account has sufficient permissions to access the groups".format(computer_group_name)
            return action_result.set_status(phantom.APP_ERROR, error_message)

        computer_group_id = response_data.get("id")

        data = {
            'intelDocId': intel_doc_id,
            'computerGroupId': computer_group_id
        }

        endpoint = '/plugin/products/detect3/api/v1/quick-scans'
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, json=data, method='post')

        if phantom.is_fail(ret_val):
            self.save_progress('Start quick scan failed')
            return action_result.get_status()

        action_result.add_data(response)

        self.save_progress('Start quick scan successful')
        message = 'Started quick scan successfully'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_list_alerts(self, param):
        """ List alerts with optional filtering.

        Args:
            param (dict): Parameters sent in by a user or playbook

        Returns:
            ActionResult status: success/failure
        """
        self.save_progress('In action handler for: {0}'.format(self.get_action_identifier()))
        action_result = self.add_action_result(ActionResult(dict(param)))

        endpoint = '/plugin/products/detect3/api/v1/alerts'
        ret_val, limit = self._validate_integer(action_result, param["limit"], TANIUMREST_LIMIT_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()
        params = {
            'limit': limit
        }
        try:
            for p in self._handle_py_ver_compat_for_input_str(param['query']).split('&'):
                k = p.split('=')[0]
                k = self._handle_py_ver_compat_for_input_str(k)
                v = p.split('=')[1]
                try:
                    params[k] = int(v)
                except ValueError:
                    params[k] = v
        except:
            self.debug_print("Unable to parse provided query")
            return action_result.set_status(phantom.APP_ERROR, "Unable to parse provided query")

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, params=params)

        if phantom.is_fail(ret_val):
            self.save_progress('List alerts failed')
            return action_result.get_status()

        try:
            for alert in response:
                details = json.loads(alert['details'])
                alert['path'] = details['match']['properties']['fullpath']
                alert['event_type'] = details['match']['type']
                md5 = details['match']['properties']['md5']
                if md5:
                    alert['md5'] = md5
                sha1 = details['match']['properties'].get('sha1')
                if sha1:
                    alert['sha1'] = sha1
                sha256 = details['match']['properties'].get('sha256')
                if sha256:
                    alert['sha256'] = sha256
                action_result.add_data(alert)
        except Exception as e:
            error_code, error_msg = self._get_error_message_from_exception(e)
            return RetVal(action_result.set_status(
                phantom.APP_ERROR,
                "Unable to parse JSON response. Error Code: {0} Error Message: {1}".format(error_code, error_msg)), None)

        action_result.update_summary({'total_alerts': len(response)})

        self.save_progress('List alerts successful')
        message = 'Listed alerts successfully'
        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_list_questions(self, param):

        self.save_progress("In action handler for: {0}".format(self.get_action_identifier()))

        action_result = self.add_action_result(ActionResult(dict(param)))

        if param.get('list_saved_questions', False):
            summary_txt = "num_saved_questions"
            ret_val, response = self._make_rest_call_helper(
                action_result, TANIUMREST_GET_SAVED_QUESTIONS, verify=self._verify, params=None, headers=None)
        else:
            summary_txt = "num_questions"
            ret_val, response = self._make_rest_call_helper(
                action_result, TANIUMREST_GET_QUESTIONS, verify=self._verify, params=None, headers=None)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        question_list = list()

        # Add the response into the data section
        for question in response.get("data", []):

            if question.get("id") and not param.get('list_saved_questions', False) and question.get('query_text') not in question_list:
                question_list.append(question.get('query_text'))
                action_result.add_data(question)

            if question.get("id") and param.get('list_saved_questions', False):
                action_result.add_data(question)

        summary = action_result.update_summary({})
        summary[summary_txt] = action_result.get_data_size()

        return action_result.set_status(phantom.APP_SUCCESS)

    def _get_response_data(self, response_data, action_result, tanium_content):

        if isinstance(response_data, list):
            if len(response_data) != 1:
                action_result.set_status(phantom.APP_ERROR, "Error occurred while fetching the {}".format(tanium_content))
                return None
            elif not isinstance(response_data[0], dict):
                action_result.set_status(phantom.APP_ERROR, "Unexpected API response")
                return None
            else:
                return response_data[0]

        elif isinstance(response_data, dict):
            return response_data

        else:
            action_result.set_status(phantom.APP_ERROR, "Unexpected API response")
            return None

    def _execute_action_support(self, param, action_result): # noqa: 901

        action_name = param['action_name']
        action_grp = self._handle_py_ver_compat_for_input_str(param['action_group'])

        package_name = self._handle_py_ver_compat_for_input_str(param['package_name'])
        package_parameter = param.get('package_parameters')

        group_name = self._handle_py_ver_compat_for_input_str(param.get('group_name'))

        # Integer validation for 'distribute_seconds' action parameter
        ret_val, distribute_seconds = self._validate_integer(
            action_result, param.get('distribute_seconds'), TANIUMREST_DISTRIBUTE_SECONDS_KEY)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Integer validation for 'expire_seconds' action parameter
        ret_val, expire_seconds = self._validate_integer(action_result, param['expire_seconds'], TANIUMREST_EXPIRE_SECONDS_KEY)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Integer validation for 'issue_seconds' action parameter
        ret_val, issue_seconds = self._validate_integer(action_result, param.get('issue_seconds'), TANIUMREST_ISSUE_SECONDS_KEY)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Get the package details
        endpoint = TANIUMREST_GET_PACKAGE.format(package=package_name)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, verify=self._verify, params=None, headers=None)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        response_data = response.get("data")

        if not response_data:
            return action_result.set_status(phantom.APP_ERROR, TANIUMREST_RESOURCE_NOT_EXIST.format(package_name, "package"))

        resp_data = self._get_response_data(response_data, action_result, "package")

        if resp_data is None:
            return action_result.get_status()

        package_id = resp_data.get("id")

        self.debug_print("Fetching parameter definition of the package")
        parameter_definition = response.get("data", {}).get("parameter_definition")

        if parameter_definition is not None:
            self.debug_print("Parameter definition fetched successfully")

        try:
            if parameter_definition and not isinstance(parameter_definition, dict):
                parameter_definition = json.loads(parameter_definition)
        except Exception as e:
            error_code, error_msg = self._get_error_message_from_exception(e)
            action_result.set_status(
                phantom.APP_ERROR,
                "Error while fetching package details. Error Code: {0}. Error Message: {1}".format(error_code, error_msg))

        if parameter_definition and len(parameter_definition.get("parameters")) != 0:
            self.debug_print("Provided package is a parameterized package")
            if package_parameter is None:
                return action_result.set_status(
                    phantom.APP_ERROR,
                    'Please provide the required package parameter in the following format\
                    :- [{"<parameter_label_1>": "<parameter_value_1>"}, {"<parameter_label_2>": "<parameter_value_2>"}]')

            try:
                package_parameter = json.loads(package_parameter)
            except Exception as e:
                error_code, error_msg = self._get_error_message_from_exception(e)
                return action_result.set_status(
                    phantom.APP_ERROR,
                    "Error while parsing the 'package_parameter' field. Error Code: {0}. Error Message: {1}"
                    .format(error_code, error_msg))

            if len(package_parameter) != len(parameter_definition.get("parameters")):
                return action_result.set_status(
                    phantom.APP_ERROR,
                    "Please provide all the required package parameters in 'package_parameter' parameter")

            param_list = list()
            invalid_keys = list()
            for param in parameter_definition.get("parameters"):
                param_list.append(param.get("key"))

            for key in list(package_parameter.keys()):
                if key not in param_list:
                    invalid_keys.append(key)

            if invalid_keys:
                return action_result.set_status(
                    phantom.APP_ERROR,
                    "The following key(s) are incorrect: {}. Please provide correct key(s)".format(', '.join(invalid_keys)))

        data = dict()
        package_param = dict()
        package_spec = {
            "source_id": package_id
        }
        if package_parameter and parameter_definition and len(parameter_definition.get("parameters")) != 0:
            for parameter_key, parameter_value in list(package_parameter.items()):
                package_param.update({"key": parameter_key, "value": parameter_value})

            package_spec.update({"parameters": [package_param]})

        if group_name:
            group_as_obj = None
            try:
                # Check to see if we are getting a group from a previous parse call. It
                # is passed in as an str representation of the python object
                group_as_obj = ast.literal_eval(group_name)
            except (SyntaxError, ValueError):
                pass

            if group_as_obj:
                data["target_group"] = group_as_obj
            else:
                endpoint = TANIUMREST_GET_GROUP.format(group_name=group_name)
                ret_val, response = self._make_rest_call_helper(
                    action_result, endpoint, verify=self._verify, params=None, headers=None)

                if phantom.is_fail(ret_val):
                    return action_result.get_status()

                response_data = response.get("data")

                if not response_data:
                    return action_result.set_status(phantom.APP_ERROR, TANIUMREST_RESOURCE_NOT_EXIST.format(group_name, "group"))

                resp_data = self._get_response_data(response_data, action_result, "group")

                if resp_data is None:
                    return action_result.get_status()

                group_id = resp_data.get("id")
                group_name = resp_data.get("name")
                data["target_group"] = {"source_id": group_id, "name": str(group_name)}

        # Get the action group details
        endpoint = TANIUMREST_GET_ACTION_GROUP.format(action_group=action_grp)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, verify=self._verify, params=None, headers=None)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        response_data = response.get("data")

        if not response_data:
            return action_result.set_status(phantom.APP_ERROR, TANIUMREST_RESOURCE_NOT_EXIST.format(action_grp, "action group"))

        resp_data = self._get_response_data(response_data, action_result, "action group")

        if resp_data is None:
            return action_result.get_status()

        action_group_id = resp_data.get("id")

        data["action_group"] = {
            "id": action_group_id
        }
        data["package_spec"] = package_spec
        data["name"] = action_name
        data["expire_seconds"] = expire_seconds

        if distribute_seconds:
            data['distribute_seconds'] = distribute_seconds

        if issue_seconds:
            data["issue_seconds"] = issue_seconds

        # make rest call
        ret_val, response = self._make_rest_call_helper(
            action_result, TANIUMREST_EXECUTE_ACTION, verify=self._verify, params=None, headers=None, json=data, method="post")

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Add the response into the data section
        action_result.add_data(response.get('data'))
        return action_result.set_status(phantom.APP_SUCCESS, "Successfully executed the action")

    def _handle_execute_action(self, param):

        self.save_progress("In action handler for: {0}".format(self.get_action_identifier()))

        action_result = self.add_action_result(ActionResult(dict(param)))

        self._execute_action_support(param, action_result)

        return action_result.get_status()

    def _determine_num_results_complete(self, data):
        """
        :param data: The object returned from a call to get question responses
        :return: tuple of num_complete, num_incomplete
        """
        self.debug_print("Data: {}".format(data))
        mr_tested = data.get("result_sets", [])[0].get("mr_tested")
        estimated_total = data.get("result_sets", [])[0].get("estimated_total")

        results = data.get("result_sets", [])
        num_complete = 0
        num_incomplete = 0

        if len(results) > 0:
            rows = results[0].get("rows", [])
            if len(rows) > 0:
                self.debug_print("MR Tested/Estimated Total: {}/{}".format(mr_tested, estimated_total))
                self.debug_print("Rows in 'determine_num_results': {}".format(json.dumps(rows, indent=2)))

            for row in rows:
                row_data_elements = row.get("data", [])
                incomplete_entry_found = False
                # data section is a list of lists
                for row_data_element in row_data_elements:
                    for results_entry in row_data_element:
                        results_text = results_entry.get("text", '')

                        if results_text in TANIUMREST_RESULTS_UNAVAILABLE:
                            incomplete_entry_found = True
                            num_incomplete += 1
                            break

                    if incomplete_entry_found:
                        break
                else:
                    num_complete += 1

        self.debug_print("Returning 'num_complete': {}, 'num_incomplete': {}".format(num_complete, num_incomplete))
        return num_complete, num_incomplete

    def _question_result(self, timeout_seconds, results_percentage, endpoint, action_result,
                         wait_for_results_processing=None, return_when_n_results_available=None,
                         wait_for_n_results_available=None):

        max_range = int(timeout_seconds / TANIUMREST_WAIT_SECONDS) + (1 if timeout_seconds % TANIUMREST_WAIT_SECONDS == 0 else 2)

        for i in range(1, max_range):
            if timeout_seconds > TANIUMREST_WAIT_SECONDS:
                if i == max_range - 1:
                    sleep(timeout_seconds - (i - 1) * TANIUMREST_WAIT_SECONDS - 1)
                else:
                    sleep(TANIUMREST_WAIT_SECONDS)
            else:
                sleep(timeout_seconds - 1)

            ret_val, response = self._make_rest_call_helper(
                action_result, endpoint, verify=self._verify, params=None, headers=None)

            if phantom.is_fail(ret_val):
                return None

            # Checking to see if all the results have been returned by the question.
            # Keeps questioning until all results have been returned.
            question_id = os.path.basename(endpoint)
            self.debug_print(
                "Checking if Tanium question ID {} has completed and returned all results . . .".format(question_id))
            data = response.get("data", {})
            mr_tested = data.get("result_sets", [])[0].get("mr_tested")
            estimated_total = data.get("result_sets", [])[0].get("estimated_total")
            if mr_tested and estimated_total:
                percentage_returned = float(mr_tested) / float(estimated_total) * 100
                self.debug_print("mr_tested: {} | est_total: {} | perc_returned: {} | results_perc: {}".format(
                    mr_tested, estimated_total, percentage_returned, results_percentage))

                # incomplete is when a sensor returns the value 'current results unavailable'
                num_results_complete, num_results_incomplete = self._determine_num_results_complete(data)
                if wait_for_results_processing:
                    num_results = num_results_complete
                else:
                    num_results = num_results_complete + num_results_incomplete

                if wait_for_results_processing and num_results_incomplete > 0:
                    # doesn't matter what percentage of results are complete, keep going until
                    # all results are complete or timeout
                    self.debug_print("Number of results incomplete: {}".format(num_results_incomplete))
                    continue
                elif return_when_n_results_available and num_results >= return_when_n_results_available:
                    self.debug_print("'wait_for_results_processing' is {}".format(wait_for_results_processing))
                    self.debug_print(
                        "Returning results because 'num_results_complete' ({}) >= 'return_when_n_results_available' ({})"
                        .format(num_results_complete, return_when_n_results_available))
                    return response
                elif wait_for_n_results_available and num_results_complete < wait_for_n_results_available:
                    self.debug_print("Waiting for {} results to finish before completing".format(wait_for_n_results_available))
                    continue
                elif int(percentage_returned) < int(results_percentage):
                    self.debug_print("Tanium question ID {} is {}% done out of {}%. Fetching more results . . ."
                                     .format(question_id, percentage_returned, results_percentage))
                    continue
                # else: return results if `columns` field present
            else:
                continue

            # reformat response data to simplify data path
            if data.get("result_sets", [])[0].get("columns"):
                rows = data.get("result_sets")[0].get("rows")
                for j in range(len(rows)):
                    formatted = []
                    for item in rows[j].get("data"):
                        formatted.append(item[0])
                    response["data"]["result_sets"][0]["rows"][j]["data"] = formatted
                return response

        else:
            action_result.set_status(
                phantom.APP_ERROR,
                "Error while fetching the results from the Tanium server in '{}' expire seconds. \
                    Please try increasing the timeout value".format(timeout_seconds))
            return None

    def _handle_list_processes(self, param):

        self.save_progress("In action handler for: {0}".format(self.get_action_identifier()))

        action_result = self.add_action_result(ActionResult(dict(param)))
        # config = self.get_config()

        sensor_name = param['sensor']
        group_name = self._handle_py_ver_compat_for_input_str(param.get('group_name'))
        timeout_seconds = param.get('timeout_seconds', 600)
        # Integer validation for 'timeout_seconds' action parameter
        ret_val, timeout_seconds = self._validate_integer(action_result, timeout_seconds, TANIUMREST_TIMEOUT_SECONDS_KEY)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        data = dict()
        data["expire_seconds"] = timeout_seconds

        if group_name:
            endpoint = TANIUMREST_GET_GROUP.format(group_name=group_name)
            ret_val, response = self._make_rest_call_helper(
                action_result, endpoint, verify=self._verify, params=None, headers=None)

            if phantom.is_fail(ret_val):
                return action_result.get_status()

            response_data = response.get("data")

            if not response_data:
                return action_result.set_status(phantom.APP_ERROR, TANIUMREST_RESOURCE_NOT_EXIST.format(group_name, "group"))

            resp_data = self._get_response_data(response_data, action_result, "group")

            if resp_data is None:
                return action_result.get_status()

            group_id = resp_data.get("id")
            data["context_group"] = {"id": group_id}

        select_list = list()
        sensor_dict = dict()
        sensor_dict["sensor"] = {"name": sensor_name}
        select_list.append(sensor_dict)
        data["selects"] = select_list

        # Ask the 'List Processes' question to Tanium
        ret_val, response = self._make_rest_call_helper(
            action_result, TANIUMREST_GET_QUESTIONS, verify=self._verify, params=None, headers=None, json=data, method="post")

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Now that the question has been processed, fetch the results from the Tanium API
        question_id = response.get("data", {}).get("id")
        self.debug_print(
            "Successfully queried Tanium for 'list_processes' action, got question results id {0}".format(question_id))
        endpoint = TANIUMREST_GET_QUESTION_RESULTS.format(question_id=question_id)

        response = self._question_result(timeout_seconds, self._percentage, endpoint, action_result)

        if response is None:
            self.debug_print("Warning! Tanium returned empty response for list_processes action")
            return action_result.get_status()

        action_result.add_data(response)

        result_sets = response.get("data", {}).get("result_sets")
        if result_sets:
            row_count = result_sets[0].get("row_count")
        else:
            self.debug_print("Warning! Tanium returned empty result set for list_processes action")
            row_count = 0

        summary = action_result.update_summary({})
        summary['num_results'] = row_count
        summary['timeout_seconds'] = timeout_seconds

        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_terminate_process(self, param):

        self.save_progress("In action handler for: {0}".format(self.get_action_identifier()))

        action_result = self.add_action_result(ActionResult(dict(param)))

        self._execute_action_support(param, action_result)

        return action_result.get_status()

    def _handle_parse_question(self, param):

        self.save_progress("In action handler for: {0}".format(self.get_action_identifier()))

        action_result = self.add_action_result(ActionResult(dict(param)))
        query_text = param['query_text']
        data = {"text": query_text}

        ret_val, response = self._make_rest_call_helper(
            action_result, TANIUMREST_PARSE_QUESTION, verify=self._verify, params=None, headers=None, json=data, method="post")
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        parsed_questions = response.get("data", [])

        for question in parsed_questions:
            action_result.add_data(question)

        summary = action_result.update_summary({})
        summary['number_of_parsed_questions'] = action_result.get_data_size()

        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_run_query(self, param):
        self.save_progress("In action handler for: {0}".format(self.get_action_identifier()))

        action_result = self.add_action_result(ActionResult(dict(param)))

        query_text = self._handle_py_ver_compat_for_input_str(param.get('query_text'))
        group_name = self._handle_py_ver_compat_for_input_str(param.get('group_name'))
        timeout_seconds = param.get('timeout_seconds', 600)
        # Integer validation for 'timeout_seconds' action parameter
        ret_val, timeout_seconds = self._validate_integer(action_result, timeout_seconds, TANIUMREST_TIMEOUT_SECONDS_KEY)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        is_saved_question = param.get('is_saved_question', False)
        summary = action_result.update_summary({})

        # parse extra question options
        wait_for_results_processing = param.get('wait_for_results_processing', False)

        # Integer validation for 'return_when_n_results_available' action parameter
        ret_val, return_when_n_results_available = self._validate_integer(
            action_result, param.get('return_when_n_results_available'), TANIUMREST_RETURN_WHEN_N_RESULTS_AVAILABLE_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Integer validation for 'wait_for_n_results_available' action parameter
        ret_val, wait_for_n_results_available = self._validate_integer(
            action_result, param.get('wait_for_n_results_available'), TANIUMREST_WAIT_FOR_N_RESULTS_AVAILABLE_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        if return_when_n_results_available and wait_for_n_results_available and return_when_n_results_available < wait_for_n_results_available:
            return action_result.set_status(
                phantom.APP_ERROR,
                "Please provide 'return_when_n_results_available' greater than or equal to 'wait_for_n_results_available'")

        if is_saved_question:
            endpoint = TANIUMREST_GET_SAVED_QUESTION.format(saved_question=query_text)

            ret_val, response = self._make_rest_call_helper(
                action_result, endpoint, verify=self._verify, params=None, headers=None)

            if phantom.is_fail(ret_val):
                return action_result.get_status()

            response_data = response.get("data")

            if not response_data:
                return action_result.set_status(
                    phantom.APP_ERROR, TANIUMREST_RESOURCE_NOT_EXIST.format(query_text, "saved question"))

            resp_data = self._get_response_data(response_data, action_result, "saved question")

            if resp_data is None:
                return action_result.get_status()

            saved_question_id = resp_data.get("id")

            endpoint = TANIUMREST_GET_SAVED_QUESTION_RESULT.format(saved_question_id=saved_question_id)

            response = self._question_result(
                timeout_seconds, self._percentage, endpoint, action_result, wait_for_results_processing,
                return_when_n_results_available, wait_for_n_results_available)

            if response is None:
                return action_result.get_status()

            action_result.add_data(response)
        else:
            question_data = self._parse_manual_question(query_text, action_result, group_name=group_name or None)
            if not question_data:
                return action_result.get_status()

            self.save_progress(json.dumps(question_data))
            response = self._ask_question(question_data, action_result, timeout_seconds, wait_for_results_processing,
                                          return_when_n_results_available, wait_for_n_results_available)
            if action_result.get_status() == phantom.APP_ERROR:
                return action_result.get_status()
            action_result.add_data(response)

        summary["timeout_seconds"] = timeout_seconds

        result_sets = response.get("data", {}).get("result_sets")
        if result_sets:
            row_count = result_sets[0].get("row_count")
        else:
            row_count = 0

        summary['number_of_rows'] = row_count

        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_get_question_results(self, param):
        self.save_progress("In action handler for: {0}".format(self.get_action_identifier()))

        action_result = self.add_action_result(ActionResult(dict(param)))

        question_id = param.get('question_id')

        # Integer validation for 'question_id' action parameter
        ret_val, question_id = self._validate_integer(action_result, question_id, TANIUMREST_QUESTION_ID_KEY, True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()
        summary = action_result.update_summary({})

        self.save_progress("Getting results for question {}".format(question_id))

        ret_val, response = self._make_rest_call_helper(
            action_result, TANIUMREST_GET_QUESTION_RESULTS.format(question_id=question_id), verify=self._verify)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, "Getting question results failed")

        action_result.add_data(response)

        result_sets = response.get("data", {}).get("result_sets")
        if result_sets:
            row_count = result_sets[0].get("row_count")
        else:
            row_count = 0

        summary['number_of_rows'] = row_count

        return action_result.set_status(phantom.APP_SUCCESS)

    def _load_full_sensors_to_obj(self, action_result, obj, param_list):
        """
        This method recursively replaces the sensor dictionary to valid key-value mapping

        :param action_result: Object of action result
        :param obj: Object to sanitize
        :param param_list: Parameter list contains values for the mapping
        :return: obj: Valid sanitized object for ask question
        """

        if isinstance(obj, list):
            return [self._load_full_sensors_to_obj(action_result, item, param_list) for item in obj]
        if isinstance(obj, dict):
            if 'sensor' in obj:
                # Process the sensor dictionary and replace in the original object
                success, obj['sensor'] = self._create_sensor_dict(action_result, obj["sensor"], param_list)
                if not success:
                    raise Exception("Error occurred during creation of sensor dictionary")
            else:
                return {k: self._load_full_sensors_to_obj(action_result, v, param_list) for k, v in obj.items()}
        return obj

    def _parameterize_query(self, query, action_result):
        """ Creates a data structure to send a parameterized sensor query to Tanium """
        selects = query["selects"]
        self.save_progress("Sensors:\n{}".format(json.dumps(selects)))
        # Set param index counter
        self._param_idx = 0
        param_list = query["parameter_values"]
        sensor_data = []

        question_data = {
            "selects": selects,
            "question_text": query["question_text"]
        }
        if "group" in query:
            question_data["group"] = query["group"]

        try:
            question_data = self._load_full_sensors_to_obj(action_result, question_data, param_list)
        except Exception as e:
            error_code, error_msg = self._get_error_message_from_exception(e)
            self.debug_print(
                "Error occurred while converting the sensors. Error code: {}, Message: {}".format(error_code, error_msg))
            return

        self.save_progress("Sensor Data:\n{}".format(json.dumps(sensor_data)))

        if self._param_idx and self._param_idx != len(param_list):
            action_result.set_status(phantom.APP_ERROR, "Please provide the exact number of parameters expected by the sensor")
            return

        return question_data

    def _create_sensor_dict(self, action_result, sensor, param_list):
        """
        This method fetches parameter definition for the provided sensor and creates key-value mapping

        :param action_result: Object of action result
        :param sensor: Sensor object to create key-value mapping
        :param param_list: Parameter list contains values for the mapping
        :return: obj: Valid sanitized object for provided sensor
        """

        sensor_name = sensor["name"]
        endpoint = TANIUMREST_GET_SENSOR_BY_NAME.format(sensor_name=sensor_name)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, verify=self._verify)
        if phantom.is_fail(ret_val):
            action_result.set_status(phantom.APP_ERROR, "Failed to get sensor definition from Tanium")
            return phantom.APP_ERROR, {}

        response_data = response.get("data")
        if not response_data:
            action_result.set_status(phantom.APP_ERROR, TANIUMREST_RESOURCE_NOT_EXIST.format(sensor_name, "sensor"))
            return phantom.APP_ERROR, {}

        resp_data = self._get_response_data(response_data, action_result, "sensor")
        if resp_data is None:
            return phantom.APP_ERROR, {}

        self.save_progress("Parameter Definition:\n{}".format(resp_data.get("parameter_definition", "")))

        raw_parameter_definition = resp_data.get("parameter_definition", "")
        parameter_definition = None
        try:
            if raw_parameter_definition:
                parameter_definition = json.loads(raw_parameter_definition)

            if not parameter_definition:
                # Regular Sensor, can use as-is
                return phantom.APP_SUCCESS, sensor
        except Exception as e:
            error_code, error_msg = self._get_error_message_from_exception(e)
            error_msg = "Error while parsing the 'parameter_definition'. Error Code: {0}. Error Message: {1}".format(
                error_code, error_msg)
            return action_result.set_status(phantom.APP_ERROR, error_msg), {}

        # Parameterized Sensor
        parameter_keys = [parameter["key"] for parameter in parameter_definition["parameters"]]
        self.save_progress("Parameter Keys:\n{}".format(json.dumps(parameter_keys)))
        parameters = []

        # Map all the keys with the respective value from parma_list
        for key in parameter_keys:
            if self._param_idx >= len(param_list):
                action_result.set_status(phantom.APP_ERROR, TANIUMREST_NOT_ENOUGH_PARAMS)
                return

            parameter = {
                "key": "||%s||" % key,
                "value": param_list[self._param_idx]
            }
            parameters.append(parameter)
            self._param_idx += 1

        # Create a new sensor dictionary with valid format
        sensor_dict = {
            "source_hash": sensor["hash"],
            "name": sensor_name,
            "parameters": parameters
        }
        return phantom.APP_SUCCESS, sensor_dict

    def _parse_manual_question(self, query_text, action_result, group_name=None):
        # Prepare data dict for posting to /questions
        data = dict()

        # If a group_name was supplied, validate the group name is valid
        if group_name:
            endpoint = TANIUMREST_GET_GROUP.format(group_name=group_name)
            ret_val, response = self._make_rest_call_helper(
                action_result, endpoint, verify=self._verify, params=None, headers=None)

            if phantom.is_fail(ret_val):
                action_result.set_status(phantom.APP_ERROR, "Failed to get group. Please provide a valid group name")
                return

            response_data = response.get("data")

            if not response_data:
                action_result.set_status(phantom.APP_ERROR, TANIUMREST_RESOURCE_NOT_EXIST.format(group_name, "group"))
                return

            resp_data = self._get_response_data(response_data, action_result, "group")

            if resp_data is None:
                return

            group_id = resp_data.get("id")
            data["context_group"] = {"id": group_id}

        # Before executing the query, run the query text against the /parse_question
        # to ensure the query is in a valid Tanium syntax
        query_to_parse = {"text": query_text}

        ret_val, response = self._make_rest_call_helper(
            action_result, TANIUMREST_PARSE_QUESTION, verify=self._verify, params=None,
            headers=None, json=query_to_parse, method="post")
        self.save_progress("Parsed Question:\n{}".format(json.dumps(response)))

        if phantom.is_fail(ret_val):
            self.debug_print("Failed to parse question")
            return

        if len(response.get("data")) != 1:
            action_result.set_status(phantom.APP_ERROR, "Please provide a valid parsed question accepted by Tanium server")
            return

        resp_text = response.get("data")[0].get("question_text", "").lower().replace('"', '').replace("'", "")
        query_text_updated = query_text.lower().replace('"', '').replace("'", "")

        if resp_text != query_text_updated:
            action_result.set_status(phantom.APP_ERROR, "Please provide a valid parsed question accepted by Tanium server")
            return

        if response["data"][0].get("parameter_values"):
            self.save_progress("Making a parameterized query")
            parameterized_data = self._parameterize_query(response.get("data")[0], action_result)
            if not parameterized_data:
                # Something failed
                return

            data.update(parameterized_data)
        else:
            self.save_progress("Making a non-parameterized query")
            data.update(response.get("data")[0])

        return data

    def _ask_question(self, data, action_result, timeout_seconds=None, wait_for_results_processing=None,
                      return_when_n_results_available=None, wait_for_n_results_available=None):
        # Post prepared data to questions endpoint and poll for results
        # config = self.get_config()
        if timeout_seconds:
            data['expire_seconds'] = timeout_seconds
        ret_val, response = self._make_rest_call_helper(
            action_result, TANIUMREST_GET_QUESTIONS, verify=self._verify, params=None, headers=None, json=data, method="post")

        if phantom.is_fail(ret_val):
            action_result.set_status(phantom.APP_ERROR, "Question post failed")
            return

        self.save_progress("Data Posted to /questions:\n{}".format(json.dumps(data)))
        self.save_progress("Response from /questions:\n{}".format(json.dumps(response)))

        question_id = response.get("data", {}).get("id")

        # Get results of Question
        endpoint = TANIUMREST_GET_QUESTION_RESULTS.format(question_id=question_id)

        response = self._question_result(timeout_seconds, self._percentage, endpoint, action_result, wait_for_results_processing,
                                         return_when_n_results_available, wait_for_n_results_available)

        if response is None:
            return None
        action_result.set_status(phantom.APP_SUCCESS)
        return response

    def handle_action(self, param):

        ret_val = phantom.APP_SUCCESS

        # Get the action that we are supposed to execute for this App Run
        action_id = self.get_action_identifier()

        self.debug_print("action_id", self.get_action_identifier())

        # Tanium API Default Actions
        if action_id == 'test_connectivity':
            ret_val = self._handle_test_connectivity(param)

        elif action_id == 'list_processes':
            ret_val = self._handle_list_processes(param)

        elif action_id == 'execute_action':
            ret_val = self._handle_execute_action(param)

        elif action_id == 'list_questions':
            ret_val = self._handle_list_questions(param)

        elif action_id == 'terminate_process':
            ret_val = self._handle_terminate_process(param)

        elif action_id == 'run_query':
            ret_val = self._handle_run_query(param)

        elif action_id == 'get_question_results':
            ret_val = self._handle_get_question_results(param)

        elif action_id == 'parse_question':
            ret_val = self._handle_parse_question(param)

        # Tanium Threat Response Actions
        elif action_id == 'list_computers':
            ret_val = self._handle_list_computers(param)

        elif action_id == 'initialize_computers_list':
            ret_val = self._handle_initialize_computers_list(param)

        elif action_id == 'list_connections':
            ret_val = self._handle_list_connections(param)

        elif action_id == 'create_connection':
            ret_val = self._handle_create_connection(param)

        elif action_id == 'delete_connection':
            ret_val = self._handle_delete_connection(param)

        elif action_id == 'list_snapshots':
            ret_val = self._handle_list_snapshots(param)

        elif action_id == 'create_snapshot':
            ret_val = self._handle_create_snapshot(param)

        elif action_id == 'delete_snapshot':
            ret_val = self._handle_delete_snapshot(param)

        elif action_id == 'get_local_snapshot':
            ret_val = self._handle_get_local_snapshot(param)

        elif action_id == 'upload_local_snapshot':
            ret_val = self._handle_upload_local_snapshot(param)

        elif action_id == 'delete_local_snapshot':
            ret_val = self._handle_delete_local_snapshot(param)

        elif action_id == 'get_process':
            ret_val = self._handle_get_process(param)

        elif action_id == 'get_process_timeline':
            ret_val = self._handle_get_process_timeline(param)

        elif action_id == 'get_process_tree':
            ret_val = self._handle_get_process_tree(param)

        elif action_id == 'get_parent_process_tree':
            ret_val = self._handle_get_parent_process_tree(param)

        elif action_id == 'get_children_process_tree':
            ret_val = self._handle_get_children_process_tree(param)

        elif action_id == 'get_events':
            ret_val = self._handle_get_events(param)

        elif action_id == 'get_events_summary':
            ret_val = self._handle_get_events_summary(param)

        elif action_id == 'list_files':
            ret_val = self._handle_list_files(param)

        elif action_id == 'save_file':
            ret_val = self._handle_save_file(param)

        elif action_id == 'delete_file':
            ret_val = self._handle_delete_file(param)

        elif action_id == 'get_file':
            ret_val = self._handle_get_file(param)

        elif action_id == 'upload_intel_doc':
            ret_val = self._handle_upload_intel_doc(param)

        elif action_id == 'start_quick_scan':
            ret_val = self._handle_start_quick_scan(param)

        elif action_id == 'list_alerts':
            ret_val = self._handle_list_alerts(param)

        # Unsupported action
        else:
            ret_val = phantom.APP_ERROR

        return ret_val

    def initialize(self):

        self._state = self.load_state()
        if not isinstance(self._state, dict):
            self.debug_print("Resetting the state file with the default format")
            self._state = {
                "app_version": self.get_app_json().get('app_version')
            }

        # Fetching the Python major version
        try:
            self._python_version = int(sys.version_info[0])
        except Exception:
            return self.set_status(phantom.APP_ERROR, "Error occurred while fetching the Phantom server's Python major version.")

        config = self.get_config()
        self._api_token = config.get('api_token')
        if self._api_token:
            self._session_id = self._api_token  # API uses token in place of session id
        else:
            self._username = self._handle_py_ver_compat_for_input_str(config.get('username'))
            self._password = config.get('password')

        if not self._api_token and not (self._username and self._password):
            return self.set_status(phantom.APP_ERROR, "Please provide either an API token, or username and password credentials")

        self._verify = config.get('verify_server_cert', False)
        self._percentage = config.get('results_percentage', 99)

        # Integer validation for 'results_percentage' configuration parameter
        ret_val, self._percentage = self._validate_integer(self, self._percentage, TANIUMREST_RESULTS_PERCENTAGE_KEY, True)
        if phantom.is_fail(ret_val):
            self.get_status()
        if self._percentage > 100:
            return self.set_status(
                phantom.APP_ERROR,
                "Please provide a valid integer in range of 0-100 in {}".format(TANIUMREST_RESULTS_PERCENTAGE_KEY)
            )

        self._base_url = self._handle_py_ver_compat_for_input_str(config['base_url'])

        # removing single occurrence of trailing back-slash or forward-slash
        if self._base_url.endswith('/'):
            self._base_url = self._base_url.strip('/').strip('\\')
        elif self._base_url.endswith('\\'):
            self._base_url = self._base_url.strip('\\').strip('/')

        # removing single occurrence of leading back-slash or forward-slash
        if self._base_url.startswith('/'):
            self._base_url = self._base_url.strip('/').strip('\\')
        elif self._base_url.startswith('\\'):
            self._base_url = self._base_url.strip('\\').strip('/')

        if not self._session_id:
            self._session_id = self._state.get('session_id', '')

        return phantom.APP_SUCCESS

    def finalize(self):

        self.save_state(self._state)
        return phantom.APP_SUCCESS


if __name__ == '__main__':

    import argparse

    import pudb

    pudb.set_trace()

    argparser = argparse.ArgumentParser()

    argparser.add_argument('input_test_json', help='Input Test JSON file')
    argparser.add_argument('-u', '--username', help='username', required=False)
    argparser.add_argument('-p', '--password', help='password', required=False)

    args = argparser.parse_args()
    session_id = None

    username = args.username
    password = args.password

    if username is not None and password is None:

        # User specified a username but not a password, so ask
        import getpass
        password = getpass.getpass("Password: ")

    if username and password:
        try:
            login_url = '{}/login'.format(TaniumRestConnector._get_phantom_base_url())

            print("Accessing the Login page")
            r = requests.get(login_url, verify=False)  # nosemgrep
            csrftoken = r.cookies['csrftoken']

            data = dict()
            data['username'] = username
            data['password'] = password
            data['csrfmiddlewaretoken'] = csrftoken

            headers = dict()
            headers['Cookie'] = 'csrftoken={}'.format(csrftoken)
            headers['Referer'] = login_url

            print("Logging into Platform to get the session id")
            r2 = requests.post(login_url, verify=False, data=data, headers=headers)  # nosemgrep
            session_id = r2.cookies['sessionid']
        except Exception as e:
            print("Unable to get session id from the platform. Error: {}".format(str(e)))
            exit(1)  # nosemgrep

    with open(args.input_test_json) as f:
        in_json = f.read()
        in_json = json.loads(in_json)
        print(json.dumps(in_json, indent=4))

        connector = TaniumRestConnector()
        connector.print_progress_message = True

        if session_id is not None:
            in_json['user_session_token'] = session_id
            connector._set_csrf_info(csrftoken, headers['Referer'])

        ret_val = connector._handle_action(json.dumps(in_json), None)
        print(json.dumps(json.loads(ret_val), indent=4))

    exit(0)  # nosemgrep
