#!/usr/bin/python
# (c) 2017, Sofer Athlan-Guyot <sathlang@redhat.com>
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
DOCUMENTATION = '''
---
module: pacemaker_is_active
short_description: Check if a resource is active.
version_added: "2.3"
author: "Sofer Athlan-Guyot (chem)"
description:
   - Check if a resource is completly started in a pacemaker cluster.
   - This works for master/slave, clone, primitive resource.
options:
    resource:
      description:
        - The name of the resource to check, without any "-clone", "-master"
          suffix.
      required: true
    max_wait:
      description:
        - How many seconds should we wait for the resource to be active.
      required: false
      default: 3

'''

EXAMPLES = '''
---
- name: Ensure galera is started
  hosts: localhost
  gather_facts: no
  tasks:
    - name: galera ready
      pacemaker_is_active:
        resource: galera
        max_wait: 10

'''

RETURN = '''
change:
  description: True if the resource is active.
  type: bool
out:
    description: A short summary of the resource.
    type: string
    sample: {"out": "Resource galera is active."}

'''

ANSIBLE_METADATA = r"""
status:
 - stableinterface
supported_by: committer
version: "1.0"
"""

# Should be at the top (flake8 E402), but ansible requires that module
# import being after metadata.
from ansible.module_utils.basic import AnsibleModule
from lxml import etree
from time import sleep
import subprocess


def master_resource_expected_count(resource_name):
    """Return the expected number of instance of a master resource.

This function takes a resource name (the resource must be of master
type) and returns the master-max attribute if present or 1 if the
attribute is not present. It raise a error in other cases..

    """

    try:
        return int(subprocess.check_output(
            ['crm_resource', '-r',
             resource_name,
             '--meta', '-g', 'master-max']
        ))
    except subprocess.CalledProcessError as e:
        if e.returncode == 6:
            return 1
        else:
            raise


def clone_resource_expected_count(resource_name):
    """Return the expected number of clone resource on the system.

This function takes a resource name which should be of type "clone"
and returns the clone-max attribute if present. If clone-max is not
present it returns the number of nodes which have the property
"$resourcename-role" set to true (composable ha). If that number is 0
(pre-composable ha), we count the number of nodes in the cluster We
raise an error in other cases.

    """
    try:
        return int(subprocess.check_output(
            ['crm_resource', '-r',
             resource_name,
             '--meta', '-g', 'clone-max'],
        ))
    except subprocess.CalledProcessError as e:
        if e.returncode == 6:
            count = int(_pipe_no_shell(['pcs', 'property'],
                                       ['grep', '-c',
                                        "{0}-role=true".format(resource_name)])
                        [0])
            if count == 0:
                return int(_pipe_no_shell(['crm_node', '-l'], ['wc', '-l'])[0])
            else:
                return count
        else:
            raise


def primitive_resource_expected_count(resource_name):
    return 1


def clone_resource_current_count(resource_name):
    return int(_filter_xpath(
        "count(//resource[@id='{0}' and {1} and {2} and {3} and {4}])"
        .format(resource_name,
                "@orphaned='false'",
                "@failed='false'",
                "@active='true'",
                "@role='Started'",
        )
    ))


def master_resource_current_count(resource_name):
    return int(_filter_xpath(
        "count(//resource[@id='{0}' and {1} and {2} and {3} and {4}])"
        .format(resource_name,
                "@orphaned='false'",
                "@failed='false'",
                "@active='true'",
                "@role='Master'",
        )
    ))


def primitive_resource_current_count(resource_name):
    return clone_resource_current_count(resource_name)


def resource_type_of(resource_name):
    """Infer the type of a resource from its name.

Using the resource name as a parameter it returns "clone", "master",
"primitive" or None if no resource matching the name could be found.

    """
    res_array = _filter_xpath(
        '//resources/*[contains(@id,"{0}")]'.format(resource_name)
    )
    if len(res_array) == 0:
        return None

    res = res_array[0]
    if res.tag == 'resource':
        return 'primitive'
    elif res.tag == 'clone':
        if res.get('multi_state') == 'false':
            return 'clone'
        elif res.get('multi_state') == 'true':
            return 'master'
        else:
            return None
    else:
        return None



def is_resource_active(mod):
    """Return success if a resource active, failure otherwise.

Takes the resource name as an argument and does the following:

  a) master/slave resources

returns active only if the needed number of masters is set e.g. galera
needs to be master on all nodes where galera is supposed to run (that
is == to the number of controllers in pre-composable ha and the number
of nodes with galera-role=true properties set in composable ha) redis
will need to have master on only one node

  b) cloned resources

returns active if the resource is started on the needed nodes
e.g. same as master/slave resources the needed number of nodes is
equal to the cluster nodes in pre-composable and to the haproxy-role
property count in composable ha

   c) primitive resources returns active

if the resource is started on one node e.g. A/P resources like
cinder-volume, VIPs

    """

    max_tries = int(mod.params["max_wait"])
    resource_name = mod.params["resource"]
    current_try = 0

    resource_type = resource_type_of(resource_name)
    if resource_type is None:
        return mod.fail_json(
            msg="Resource '{0}' doesn't exist in the cib."
            .format(resource_name)
        )

    expected_count_fun = {
        "master": master_resource_expected_count,
        "clone": clone_resource_expected_count,
        "primitive": primitive_resource_expected_count,
    }
    current_count_fun = {
        "master": master_resource_current_count,
        "clone": clone_resource_current_count,
        "primitive": primitive_resource_current_count,
    }
    resource_expected_count = expected_count_fun[resource_type](resource_name)
    resource_current_count = current_count_fun[resource_type](resource_name)

    while resource_expected_count != resource_current_count:
        if current_try >= max_tries-1:
            return mod.fail_json(
                msg="Max wait time of {0} second reached waiting for {1}"
                .format(max_tries, resource_name)
            )
        sleep(1)
        current_try += 1
        resource_current_count = current_count_fun[resource_type](resource_name)

    mod.exit_json(msg="Resource {0} is active".format(resource_name),
                  changed=True)


def _pipe_no_shell(cmd1_array, cmd2_array):
    "Pipe cmd1_array into cmd2_array without using shell interpolation."
    cmd1 = subprocess.Popen(cmd1_array, stdout=subprocess.PIPE)
    cmd2 = subprocess.Popen(cmd2_array,
                            stdin=cmd1.stdout,
                            stdout=subprocess.PIPE)
    return cmd2.communicate()


def _filter_xpath(xpath):
    "Filter the cib on some xpath."
    xml_string = subprocess.check_output(['crm_mon', '-r', '--as-xml'])
    tree = etree.fromstring(str(xml_string))
    return tree.xpath(xpath)


def main():
    "Main function called by Ansible."
    mod = AnsibleModule(
        argument_spec=dict(
            resource=dict(required=True),
            max_wait=dict(default=5),  # in seconds
        )
    )

    is_resource_active(mod)


if __name__ == '__main__':
    main()
