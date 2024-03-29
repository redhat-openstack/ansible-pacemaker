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

import time
from distutils.version import StrictVersion

DOCUMENTATION = '''
---
module: pacemaker_cluster
short_description: Manage a pacemaker cluster
version_added: "2.3"
author: "Mathieu Bultel (matbu)"
description:
   - This module can manage a pacemaker cluster and nodes from Ansible using
     the pacemaker cli.
options:
    state:
      description:
        - Indicate desired state of the cluster
      choices: ['online', 'offline', 'restart', 'cleanup']
      required: true
    check_and_fail:
      description:
        - Exit if the current state is not the one indicated in the state option
      required: false
      default: false
    node:
      description:
        - Specify which node of the cluster you want to manage. None == the
          cluster status itself, 'all' == check the status of all nodes.
      required: false
      default: None
    timeout:
      description:
        - Timeout when the module should considered that the action has failed
      required: false
      default: 300
    force:
      description:
        - Force the change of the cluster state
      required: false
      default: true
requirements:
    - "python >= 2.6"
'''
EXAMPLES = '''
---
- name: Set cluster Online
  hosts: localhost
  gather_facts: no
  tasks:
    - name: get cluster state
      pacemaker_cluster: state=online
'''

RETURN = '''
change:
    description: True if the cluster state has changed
    type: bool
out:
    description: The output of the current state of the cluster. It return a
                 list of the nodes state.
    type: string
    sample: "out": [["  overcloud-controller-0", " Online"]]}
rc:
    description: exit code of the module
    type: bool
'''

def get_cluster_status(module):
    cmd_partition = "crm_node -q"
    partition_rc, partition_out, partition_err = module.run_command(cmd_partition)
    if partition_out.strip() != "1": # we're not in a quorate partition or cluster is down
        return 'offline'
    cmd = "pcs cluster status"
    rc, out, err = module.run_command(cmd)
    if rc != 0:
        return 'offline'
    else:
        return 'online'

def get_node_status(module, node='all'):
    if node == 'all':
        cmd = "pcs cluster pcsd-status %s" % node
    else:
        cmd = "pcs cluster pcsd-status"
    rc, out, err = module.run_command(cmd)
    if rc is 1:
        module.fail_json(msg="Command execution failed.\nCommand: `%s`\nError: %s" % (cmd, err))
    status = []
    for o in out.splitlines():
        status.append(o.split(':'))
    return status

def clean_cluster(module, timeout):
    cmd = "pcs resource cleanup"
    rc, out, err = module.run_command(cmd)
    if rc is 1:
        module.fail_json(msg="Command execution failed.\nCommand: `%s`\nError: %s" % (cmd, err))

def set_cluster(module, state, timeout, force):
    if state == 'online':
        cmd = "pcs cluster start"
    if state == 'offline':
        cmd = "pcs cluster stop"
        if force:
            cmd = "%s --force" % cmd
    rc, out, err = module.run_command(cmd)
    if rc is 1:
        module.fail_json(msg="Command execution failed.\nCommand: `%s`\nError: %s" % (cmd, err))

    t = time.time()
    ready = False
    while time.time() < t+timeout:
        cluster_state = get_cluster_status(module)
        if cluster_state == state:
            ready = True
            break
    if not ready:
        module.fail_json(msg="Failed to set the state `%s` on the cluster\n" % (state))

def set_node(module, state, timeout, force, node='all'):
    # map states
    if state == 'online':
        cmd = "pcs cluster start"
    if state == 'offline':
        cmd = "pcs cluster stop"
        if force:
            cmd = "%s --force" % cmd

    nodes_state = get_node_status(module, node)
    for node in nodes_state:
        if node[1].strip().lower() != state:
            cmd = "%s %s" % (cmd, node[0].strip())
            rc, out, err = module.run_command(cmd)
            if rc is 1:
                module.fail_json(msg="Command execution failed.\nCommand: `%s`\nError: %s" % (cmd, err))

    t = time.time()
    ready = False
    while time.time() < t+timeout:
        nodes_state = get_node_status(module)
        for node in nodes_state:
            if node[1].strip().lower() == state:
                ready = True
                break
    if not ready:
        module.fail_json(msg="Failed to set the state `%s` on the cluster\n" % (state))

def main():
    argument_spec = dict(
        state = dict(choices=['online', 'offline', 'restart', 'cleanup']),
        check_and_fail=dict(default=False, type='bool'),
        node  = dict(default=None),
        timeout=dict(default=300, type='int'),
        force=dict(default=True, type='bool'),
    )

    module = AnsibleModule(argument_spec,
        supports_check_mode=True,
    )
    changed = False
    check_and_fail = module.params['check_and_fail']
    state = module.params['state']
    node = module.params['node']
    force = module.params['force']
    timeout = module.params['timeout']

    if state in ['online', 'offline']:
        # Get cluster status
        if node is None:
            cluster_state = get_cluster_status(module)
            if cluster_state == state:
                module.exit_json(changed=changed,
                         out=cluster_state)
            else:
                if check_and_fail:
                    module.fail_json(msg="State not found to be in %s " % state)
                set_cluster(module, state, timeout, force)
                cluster_state = get_cluster_status(module)
                if cluster_state == state:
                    module.exit_json(changed=True,
                         out=cluster_state)
                else:
                    module.fail_json(msg="Fail to bring the cluster %s" % state)
        else:
            cluster_state = get_node_status(module, node)
            # Check cluster state
            for node_state in cluster_state:
                if node_state[1].strip().lower() == state:
                    module.exit_json(changed=changed,
                             out=cluster_state)
                else:
                    if check_and_fail:
                        module.fail_json(msg="State not found to be in %s " % state)
                    # Set cluster status if needed
                    set_cluster(module, state, timeout, force)
                    cluster_state = get_node_status(module, node)
                    module.exit_json(changed=True,
                             out=cluster_state)

    if state in ['restart']:
        set_cluster(module, 'offline', timeout, force)
        cluster_state = get_cluster_status(module)
        if cluster_state == 'offline':
            set_cluster(module, 'online', timeout, force)
            cluster_state = get_cluster_status(module)
            if cluster_state == 'online':
                module.exit_json(changed=True,
                     out=cluster_state)
            else:
                module.fail_json(msg="Failed during the restart of the cluster, the cluster can't be started")
        else:
            module.fail_json(msg="Failed during the restart of the cluster, the cluster can't be stopped")

    if state in ['cleanup']:
        set_cluster(module, state, timeout, force)
        module.exit_json(changed=True,
                 out=cluster_state)

from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
