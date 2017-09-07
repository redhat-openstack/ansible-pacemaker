#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2016, Mathieu Bultel <mbultel@redhat.com>
#
#   Copyright Red Hat, Inc. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.

from distutils.version import StrictVersion
import time

DOCUMENTATION = '''
---
module: pacemaker_manage
short_description: Manage a pacemaker resource
extends_documentation_fragment: openstack
version_added: "2.2"
author: "Mathieu Bultel (matbu)"
description:
   - Manage a pacemaker resource from Ansible
options:
    state:
      description:
        - Indicate desired state of the cluster
      choices: ['manage', 'unmanage', 'enable', 'disable', 'restart',
                'show', 'delete', 'started', 'master']
      required: true
    resource:
      description:
        - Specify which resource you want to handle
      required: false
      default: None
    timeout:
      description:
        - Timeout when the module should considered that the action has failed
      required: false
      default: 300
    check_mode:
        description:
          - Check only the status of the resource
        required: false
        default: false
    wait_for_resource:
        description:
          - Wait for resource to get the required state, will failed if the
            timeout is reach
        required: false
        default: false
requirements:
    - "python >= 2.6"
'''
EXAMPLES = '''
---
- name: Manage Pacemaker resources
  hosts: localhost
  gather_facts: no
  tasks:
    - name: enable haproxy
      pacemaker_resource: state=enable resource=haproxy
'''

RETURN = '''

'''


def check_resource_state(module, resource, state):
    # get resources
    cmd = "bash -c 'pcs status --full | grep -w \"%s[ \t]\"'" % resource
    rc, out, err = module.run_command(cmd)
    if state in out.lower():
        return True


def get_resource(module, resource):
    cmd = "pcs resource show %s" % resource
    rc, out, err = module.run_command(cmd)
    return out


def set_resource_state(module, resource, state, timeout):
    cmd = "pcs resource %s %s --wait=%s" % (state, resource, timeout)
    return module.run_command(cmd)


def main():
    argument_spec = dict(
        state=dict(choices=['manage', 'unmanage', 'enable', 'disable',
                            'restart', 'show', 'delete', 'started',
                            'stopped', 'master']),
        resource=dict(default=None),
        timeout=dict(default=300, type='int'),
        check_mode=dict(default=False, type='bool'),
        wait_for_resource=dict(default=False, type='bool'),
    )

    module = AnsibleModule(argument_spec, supports_check_mode=True)
    changed = False
    state = module.params['state']
    resource = module.params['resource']
    timeout = module.params['timeout']
    check_mode = module.params['check_mode']
    wait_for_resource = module.params['wait_for_resource']

    if check_mode:
        if check_resource_state(module, resource, state):
            module.exit_json(changed=False,
                             out={'resource': resource, 'status': state})
        else:
            if wait_for_resource:
                t = time.time()
                status = False
                while time.time() < t+timeout:
                    if check_resource_state(module, resource, state):
                        status = True
                        break
                if status:
                    module.exit_json(changed=False,
                                     out={'resource': resource,
                                          'status': state})
            module.fail_json(msg="Failed, the resource %s is not %s\n" %
                             (resource, state))

    # TODO: check state before doing anything:
    resource_state = get_resource(module, resource)
    # if resource_state = state:
    rc, out, err = set_resource_state(module, resource, state, timeout)
    if rc == 1:
        module.fail_json(msg="Failed, to set the resource %s to the state"
                         "%s" % (resource, state),
                         rc=rc,
                         output=out,
                         error=err)
    module.exit_json(changed=True, out=out, rc=rc)

from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
