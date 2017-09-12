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
import subprocess
from time import sleep
from ansible.module_utils.basic import AnsibleModule
from lxml import etree


class Resource(object):
    "Base clase for resource and resource factory."
    get_type = None

    def _filter_xpath_crmmon(self, xpath):
        "Filter the crmmon xml output on some xpath."
        xml_string = self.mod.run_command(['crm_mon', '-r', '--as-xml'],
                                          {'check_rc': True})[1]
        tree = etree.fromstring(str(xml_string))
        return tree.xpath(xpath)

    def _filter_xpath_cib(self, xpath):
        "Filter the cib on some xpath."
        xml_string = self.mod.run_command(['cibadmin', '-l', '--query'],
                                          {'check_rc': True})[1]
        tree = etree.fromstring(str(xml_string))
        return tree.xpath(xpath)

    def _current_count(self, role):
        "Calculate the current active instance."
        return int(self._filter_xpath_crmmon(
            "count(//resource[@id='{0}' and {1} and {2} and {3} and {4}])"
            .format(self.name,
                    "@orphaned='false'",
                    "@failed='false'",
                    "@active='true'",
                    "@role='{0}'".format(role),
            )
        ))

    def _get_crm_resource(self, prop):
        return self.mod.run_command(
            ['crm_resource', '-r',
             self.name,
             '--meta', '-g', prop]
        )

    def _get_cib(self):
        return self.mod.run_command(
            ['cibadmin', '-l', '--query']
        )

    def _create_result(self, msg):
        return {
            'resource_type': self.get_type,
            'resource_name': self.name,
            'msg': msg,
        }

    def __init__(self, mod, resource_name):
        self.mod = mod
        self.name = resource_name

    def fail(self, msg):
        result = self._create_result(msg)
        return self.mod.fail_json(**result)

    def success(self, msg):
        result = self._create_result(msg)
        result['changed'] = False
        return self.mod.exit_json(**result)

    def from_type(self):
        """Infer the type of a resource from its name.  Factory method.

        Using the resource name as a parameter it returns a "Clone",
        "Master", "Primitive" instance.  If no resource matching the name
        could be found, it return a "Resource" instance.

        """
        res_array = self._filter_xpath_crmmon(
            '//resources/*[contains(@id,"{0}")]'.format(self.name)
        )
        if len(res_array) == 0:
            return self

        res = res_array[0]
        if res.tag == 'resource':
            return Primitive(self.mod, self.name)
        elif res.tag == 'clone':
            if res.get('multi_state') == 'false':
                return Clone(self.mod, self.name)
            elif res.get('multi_state') == 'true':
                return Master(self.mod, self.name)
        elif res.tag == 'bundle':
            return Bundle(self.mod, self.name)

        return self

class Bundle(Resource):
    "Representation of a bundle resource."
    get_type = 'bundle'

    def __init__(self, mod, resource_name):
        super(Bundle, self).__init__(mod, resource_name)
        self.primitive_name = self._get_primitive_name()

    # Returns the primitive name running inside the bundle
    # It will be an empty string in case the bundle does not
    # contain a primitive (e.g. haproxy-bundle)
    def _get_primitive_name(self):
        return self._filter_xpath_cib(
           'string(//resources/bundle[@id="{0}"]/primitive/@id)'
           .format(self.name)
        )

    # get the configured number of masters from the CIB
    def _get_bundle_masters(self):
        ret = self._filter_xpath_cib(
           'string(//resources/bundle[@id="{0}"]/docker/@masters)'
           .format(self.name)
        )
        try:
            return int(ret)
        except ValueError:
            return 0

    # get the configured number of replicas from the CIB
    def _get_bundle_replicas(self):
        ret = self._filter_xpath_cib(
           'string(//resources/bundle[@id="{0}"]/docker/@replicas)'
           .format(self.name)
        )
        try:
            return int(ret)
        except ValueError:
            return 0

    # count the number of running masters (checks done via the primitive
    # name running inside the bundle
    def _get_bundle_running_masters(self):
        return int(self._filter_xpath_crmmon(
           'count(//resource[@id="{0}" and @orphaned="false" and @failed="false"' \
           ' and @active="true" and @role="Master"])'
           .format(self.primitive_name)
        ))

    # count the number of replicas when we have a primitive inside the bundle
    def _get_bundle_running_replicas(self):
        return int(self._filter_xpath_crmmon(
           'count(//resource[@id="{0}" and @orphaned="false" and @failed="false"' \
           ' and @active="true" and @role="Started"])'
           .format(self.primitive_name)
        ))

    # count the number of replicas when we have a simple bundle
    def _get_bundle_running_containers(self):
        return int(self._filter_xpath_crmmon(
           'count(//bundle[@id="{0}"]/replica/resource[@orphaned="false" and @failed="false"' \
           ' and @active="true" and @role="Started"])'
           .format(self.name)
        ))

    def _is_bundle_master(self):
        return (self._get_bundle_masters() > 0)

    # Returns true if the bundle has a primitive inside (redis, galera, rabbitmq)
    def _is_bundle_ocf(self):
        return (self.primitive_name != "")

    def expected_count(self):
        """Return the expected number of instance of a bundle resource.

        This function takes a resource name (the resource must be of bundle
        type) and returns the expected count depending on the number of replicas
        configured on the bundle.

        """
        if self._is_bundle_ocf(): # master/slave or clone inside the bundle
            if self._is_bundle_master():
                expected_count = self._get_bundle_masters()
            else:
                expected_count = self._get_bundle_replicas()
        else: # plain docker bundle without ocf resources inside
            expected_count = self._get_bundle_replicas()

        return int(expected_count)

    def current_count(self):
        "Calculate the current active instance."
        if self._is_bundle_ocf(): # master/slave or clone inside the bundle
            if self._is_bundle_master():
                current_count = self._get_bundle_running_masters()
            else:
                current_count = self._get_bundle_running_replicas()
        else: # plain docker bundle without ocf resources inside
            current_count = self._get_bundle_running_containers()

        return int(current_count)

class Master(Resource):
    "Representation of a master/slave resource."
    get_type = 'master'

    def expected_count(self):
        """Return the expected number of instance of a master resource.

        This function takes a resource name (the resource must be of master
        type) and returns the master-max attribute if present or 1 if the
        attribute is not present. It raise a error in other cases..

        """

        rc, stdout, stderr = self._get_crm_resource('master-max')
        if rc == 0:
            return int(stdout)
        elif rc == 6:
            return 1

        return self.fail(
            "Unknow error geting crm_resource for master '{0}'."
            .format(self.name)
        )

    def current_count(self):
        "Calculate the current active instance."
        return self._current_count('Master')


class Clone(Resource):
    "Representation of a clone resource."
    get_type = 'clone'

    def _pipe_no_shell(self, cmd1_array, cmd2_array):
        "Pipe cmd1_array into cmd2_array without using shell interpolation."
        self.mod.get_bin_path(cmd1_array[0], required=True)
        self.mod.get_bin_path(cmd2_array[0], required=True)
        cmd1 = subprocess.Popen(cmd1_array, stdout=subprocess.PIPE)
        cmd2 = subprocess.Popen(cmd2_array,
                                stdin=cmd1.stdout,
                                stdout=subprocess.PIPE)
        return cmd2.communicate()

    def expected_count(self):
        """Return the expected number of clone resource on the system.

        This function takes a resource name which should be of type
        "clone" and returns the clone-max attribute if present. If
        clone-max is not present it returns the number of nodes which
        have the property "$resourcename-role" set to true (composable
        ha). If that number is 0 (pre-composable ha), we count the
        number of nodes in the cluster We raise an error in other
        cases.

        """
        rc, stdout, stderr = self._get_crm_resource('clone-max')
        if rc == 0:
            return int(stdout)
        elif rc == 6:
            count = int(self._pipe_no_shell(
                ['pcs', 'property'],
                ['grep', '-c',
                 "{0}-role=true".format(self.name)]
            )[0])
            if count == 0:
                return int(self._pipe_no_shell(['crm_node', '-l'],
                                               ['wc', '-l'])[0])
            else:
                return count

        return self.fail(
            "Unknow error geting crm_resource for master '{0}'."
            .format(self.name)
        )

    def current_count(self):
        "Calculate the current active instance."
        return self._current_count("Started")


class Primitive(Clone):
    "Representation of a primitive resource."
    get_type = 'primitive'

    def expected_count(self):
        return 1


def is_resource_active(mod):
    """Return success if a resource active, failure otherwise.

    Takes the resource name as an argument and does the following:

    a) master/slave resources

    Returns active only if the needed number of masters is set
    e.g. galera needs to be master on all nodes where galera is
    supposed to run (that is == to the number of controllers in
    pre-composable ha and the number of nodes with galera-role=true
    properties set in composable ha) redis will need to have master on
    only one node.

    b) cloned resources

    Returns active if the resource is started on the needed nodes
    e.g. same as master/slave resources the needed number of nodes is
    equal to the cluster nodes in pre-composable and to the
    haproxy-role property count in composable ha.

    c) primitive resources returns active

    If the resource is started on one node e.g. A/P resources like
    cinder-volume, VIPs.

    """

    max_tries = int(mod.params["max_wait"])
    resource_name = mod.params["resource"]
    current_try = 0

    resource = Resource(mod, resource_name).from_type()
    if resource.get_type is None:
        return resource.fail("Resource '{0}' doesn't exist in the cib.".format(
            resource.name
        ))

    resource_expected_count = resource.expected_count()
    while resource_expected_count != resource.current_count():
        if current_try >= max_tries-1:
            return resource.fail(
                "Max wait time of {0} seconds reached waiting for {1}".format(
                    max_tries, resource.name
                ))
        sleep(1)
        current_try += 1
    return resource.success("{0} resource {1} is active".format(resource.get_type,
                                                                resource.name))


def main():
    "Main function called by Ansible."
    mod = AnsibleModule(
        argument_spec=dict(
            resource=dict(required=True),
            max_wait=dict(default=5),  # in seconds
        )
    )

    return is_resource_active(mod)


if __name__ == '__main__':
    main()
