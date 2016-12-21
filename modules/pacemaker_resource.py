#!/usr/bin/python
#coding: utf-8 -*-

# (c) 2016, Mathieu Bultel <mbultel@redhat.com>
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

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
