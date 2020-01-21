#!/usr/bin/python
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

ANSIBLE_METADATA = {'status': ['preview'],
                    'supported_by': 'community',
                    'version': '0.1'}

DOCUMENTATION = '''
---
module: statuscake_ssl
short_description: Manage StatusCake SSL tests
description:
    - Manage StatusCake SSL tests by using StatusCake REST API.
version_added: "2.2"
author: "Raphael Pereira Ribeiro (@raphapr)"
options:
  username:
    description:
      - StatusCake account username. Can also be supplied via $STATUSCAKE_USERNAME env variable.
    required: false
  api_key:
    description:
      - StatusCake API KEY. Can also be supplied via $STATUSCAKE_API_KEY env variable.
    required: false
  domain:
    description:
      - URL to check, has to start with https://
    required: true
  state:
    description:
      - Attribute that specifies if the SSL test has to be created, deleted or a basic list of all SSL tests.
    required: false
    default: present
    choices: ['present', 'absent', 'list']
  checkrate:
    description:
      - Checkrate in seconds.
    required: false
    default: 3600
    choices: [300, 600, 1800, 3600, 86400, 2073600]
  contact_group:
    description:
      - Contact group ID
    required: True
  alert_at:
    description:
      - When you wish to receive reminders. Must be exactly 3 numeric values separated by commas
    default: "1,7,30"
    required: false
  alert_expiry:
    description:
    - Set to true to enable expiration alerts. False to disable
    default: true
    required: false
  alert_reminder:
    description:
      - Set to true to enable reminder alerts. False to disable. Also see alert_at
    default: true
    required: false
  alert_broken:
    description:
      - Set to true to enable broken alerts. False to disable
    default: true
    required: false
  alert_mixed:
    description:
      - Set to true to enable mixed content warnings. False to disable
    default: true
    required: false
  statuscake_timeout:
    description:
      - Specifies idle timeout (in seconds) for the connection. Yu may want to increase this in order to avoid timeout from StatusCake API.
    default: true
    required: false
'''

EXAMPLES = '''
---
- name: Create statuscake test
  statuscake_ssl:
    username: user
    api_key: api
    domain: "https://example.com"
    checkrate: 86400
    contact_group: 1503
    alert_at: 59,60,61
    alert_expiry: false
    alert_reminder: false
    alert_broken: false
    alert_mixed: true
'''

from ansible.module_utils.basic import *
from ansible.module_utils.urls import fetch_url, open_url
from ansible.module_utils._text import to_native
from ansible.module_utils.six.moves.urllib.parse import urlencode


class StatusCakeSSL:
    URL_UPDATE_TEST = "https://app.statuscake.com/API/SSL/Update"
    URL_DETAILS_TEST = "https://app.statuscake.com/API/SSL/Update?id={ssl_id}"
    URL_ALL_TESTS = "https://app.statuscake.com/API/SSL"

    def __init__(self, module, username, api_key, state, domain, checkrate,
                 contact_group, alert_at, alert_expiry, alert_reminder,
                 alert_broken, alert_mixed, statuscake_timeout):

        self.headers = {"Username": username, "API": api_key}
        self.module = module
        self.state = state
        self.domain = domain
        self.checkrate = checkrate
        self.contact_group = contact_group
        self.alert_at = alert_at
        self.alert_expiry = alert_expiry
        self.alert_reminder = alert_reminder
        self.alert_broken = alert_broken
        self.alert_mixed = alert_mixed
        self.statuscake_timeout = statuscake_timeout

        if not statuscake_timeout:
            self.statuscake_timeout = 10
        else:
            self.statuscake_timeout = statuscake_timeout

        self.data = {"domain": self.domain,
                     "checkrate": self.checkrate,
                     "contact_groups": self.contact_group,
                     "alert_at": self.alert_at,
                     "alert_expiry": self.alert_expiry,
                     "alert_reminder": self.alert_reminder,
                     "alert_broken": self.alert_broken,
                     "alert_mixed": self.alert_mixed,
                     }

        self.result = {
            'changed': False,
            'domain': self.domain,
            'state': self.state,
            'diff': {
                'before': {},
                'after': {}
            }
        }

    def get_all_tests(self):
        response = self.request(self.URL_ALL_TESTS)
        del self.result['domain']
        del self.result['state']
        self.result.update({'tests': {'output': response.json(),
                            'count': len(response.json())}})

    def check_response(self, response):
        if response.get('Success'):
            self.result['changed'] = True

    def check_test(self):
        response = self.request(self.URL_ALL_TESTS)

        for item in response:
            if item['domain'] == self.domain:
                return {"alert_at": item['alert_at'],
                        "alert_broken": item['alert_broken'],
                        "alert_expiry": item['alert_expiry'],
                        "alert_reminder": item['alert_reminder'],
                        "alert_mixed": item['alert_mixed'],
                        "contact_groups": item['contact_groups'][0],
                        "domain": item['domain'],
                        "id": item['id']
                        }

    def delete_test(self):
        test = self.check_test()

        if not test:
            self.result['response'] = "Test not found on this account"
        else:
            test_id = test['id']
            if self.module.check_mode:
                self.result['changed'] = True
                self.result['response'] = ("Deletion successful")
            else:
                response = self.request(self.URL_DETAILS_TEST.format(ssl_id=test_id),
                                        method='DELETE')
                self.check_response(response)

    def create_test(self):
        req_data = self.check_test()

        if not req_data:
            if self.module.check_mode:
                self.result['changed'] = True
                self.result['response'] = "SSL test inserted"
            else:
                response = self.request(self.URL_UPDATE_TEST,
                                        method='PUT',
                                        payload=urlencode(self.data))
                self.result['response'] = "SSL test inserted"
                self.check_response(response)
        else:
            test_id = req_data['id']
            diffkeys = ([k for k in self.data if k in self.data.keys() and
                        k != "checkrate" and
                        str(self.data[k]) != str(req_data[k])])
            if self.module.check_mode:
                if len(diffkeys) != 0:
                    self.result['changed'] = True
                    self.result['response'] = ("SSL has been updated " +
                                               "successfully.")
                else:
                    self.result['response'] = ("No data has been updated " +
                                               "(is any data different?) " +
                                               "Given: "+str(test_id))
            else:
                if len(diffkeys) == 0:
                    self.result['response'] = ("No data has been updated " +
                                               "(is any data different?) " +
                                               "Given: "+str(test_id))
                else:
                    self.data.pop('domain')
                    self.data['id'] = test_id
                    response = self.request(self.URL_UPDATE_TEST,
                                            method='PUT',
                                            payload=urlencode(self.data))
                    self.check_response(response)
            self.result['diff']['before'] = {k: req_data[k] for k in diffkeys}
            self.result['diff']['after'] = {k: self.data[k] for k in diffkeys}

    def get_result(self):
        result = self.result
        return result

    def request(self, url, method=None, payload=None):
        """Generic HTTP method for StatusCake requests."""

        if method is not None:
            self.method = method
        else:
            self.method = 'GET'

        resp, info = fetch_url(self.module, url,
                               headers=self.headers,
                               data=payload,
                               method=self.method,
                               timeout=self.statuscake_timeout
                               )

        if info['status'] >= (500 or -1):
            self.module.fail_json(msg='Request failed for {url}: {status} - {msg}'.format(**info))
        elif info['status'] >= 300:
            self.module.fail_json(msg='Request failed for {url}: {status} - {msg}'.format(**info),
                                  body=self.module.jsonify((to_native(info['body']))))

        try:
            return self.module.from_json(to_native(resp.read()))
        except:
            return self.module.fail_json(msg=info)


def run_module():

    module_args = dict(
        username=dict(type='str', required=False),
        api_key=dict(type='str', required=False),
        state=dict(choices=['absent', 'present', 'list'], default='present'),
        domain=dict(type='str', required=False),
        checkrate=dict(type='int', required=False, default=3600),
        contact_group=dict(type='int', required=False),
        alert_at=dict(type='str', required=False, default="1,7,30"),
        alert_expiry=dict(type='bool', required=False, default=True),
        alert_reminder=dict(type='bool', required=False, default=True),
        alert_broken=dict(type='bool', required=False, default=True),
        alert_mixed=dict(type='bool', required=False, default=True),
        statuscake_timeout=dict(type='int', required=False, default=True)
    )

    module = AnsibleModule(
            argument_spec=module_args,
            supports_check_mode=True,
            required_if=[
              ["state", "present", ["domain", "contact_group"]],
              ["state", "absent", ["domain"]],
            ]
            )

    username = module.params['username']
    api_key = module.params['api_key']
    state = module.params['state']
    domain = module.params['domain']
    checkrate = module.params['checkrate']
    contact_group = module.params['contact_group']
    alert_at = module.params['alert_at']
    alert_expiry = module.params['alert_expiry']
    alert_reminder = module.params['alert_reminder']
    alert_broken = module.params['alert_broken']
    alert_mixed = module.params['alert_mixed']
    statuscake_timeout = module.params['statuscake_timeout']

    if not (username and api_key) and \
            os.environ.get('STATUSCAKE_USERNAME') and \
            os.environ.get('STATUSCAKE_API_KEY'):
        username = os.environ.get('STATUSCAKE_USERNAME')
        api_key = os.environ.get('STATUSCAKE_API_KEY')
    if not (username and api_key) and \
            not (os.environ.get('STATUSCAKE_USERNAME') and \
            os.environ.get('STATUSCAKE_API_KEY')):
        module.fail_json(msg="You must set STATUSCAKE_USERNAME and " +
                             "STATUSCAKE_API_KEY environment variables " +
                             "or set username/api_key module arguments")

    test = StatusCakeSSL(module,
                         username,
                         api_key,
                         state,
                         domain,
                         checkrate,
                         contact_group,
                         alert_at,
                         alert_expiry,
                         alert_reminder,
                         alert_broken,
                         alert_mixed,
                         statuscake_timeout)

    if state == "absent":
        test.delete_test()
    if state == "present":
        test.create_test()
    if state == "list":
        test.get_all_tests()

    result = test.get_result()
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
