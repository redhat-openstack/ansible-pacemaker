#!/usr/bin/python
#coding: utf-8 -*-

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
      choices: ['manage', 'unmanage', 'enable', 'disalbe', 'restart', 'show', 'delete']
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
requirements:
    - "python >= 2.6"
    - "shade"
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

def get_resource_state(module, resource):
    cmd = "pcs resource show %s" % resource
    rc, out, err = module.run_command(cmd)
    return out

def get_resource(module):
    return True

def set_resource_state(module, resource, state, timeout):
    cmd = "pcs resource %s %s --wait=%s" % (state, resource, timeout)
    rc, out, err = module.run_command(cmd)
    return out

def main():
    argument_spec = dict(
        state = dict(choices=['manage', 'unmanage', 'enable', 'disalbe', 'restart', 'show', 'delete', 'started', 'stopped']),
        resource  = dict(default=None),
        timeout=dict(default=300, type='int'),
    )

    module = AnsibleModule(argument_spec,
        supports_check_mode=True,
    )
    changed = False
    state = module.params['state']
    resource = module.params['resource']
    timeout = module.params['timeout']

    #TODO: check state before doing anything:
    resource_state = get_resource_state(module, resource)
    # if resource_state = state:
    out = set_resource_state(module, resource, state, timeout)
    module.exit_json(changed=True,
         out=out)

from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
