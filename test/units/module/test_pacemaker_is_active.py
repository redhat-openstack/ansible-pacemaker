from ansible.compat.tests import unittest
from ansible.compat.tests.mock import call, create_autospec, patch
from ansible.module_utils.basic import AnsibleModule

from modules import pacemaker_is_active
import subprocess
import json

class TestResourceTypeOf(unittest.TestCase):
    @patch('subprocess.check_output')
    def test__resource_type_of__happy_path(self, check_output):
        xml_string = ''
        with open("./test/units/module/cluster_good.xml", "r") as myfile:
            xml_string = myfile.read()
        check_output.return_value = xml_string

        expected_result = {
            'haproxy': 'clone',
            'galera': 'master',
            'openstack-cinder-volume': 'primitive',
            'ip-192.168.24.10': 'primitive',
        }

        for resource_name, expected_type in expected_result.iteritems():
            found_type = pacemaker_is_active.resource_type_of(resource_name)
            self.assertEqual(found_type, expected_type)


class TestResourceExpectedCount(unittest.TestCase):
    @patch('subprocess.check_output')
    def test__master__happy_path(self, check_output):
        check_output.return_value = "3\n"
        count = pacemaker_is_active.master_resource_expected_count('galera')
        self.assertEqual(count, 3)

    @patch('subprocess.check_output')
    def test__master__catch_error(self, check_output):
        check_output.return_value = "\n"
        check_output.side_effect = subprocess.CalledProcessError(6, '', '')
        count = pacemaker_is_active.master_resource_expected_count('galera')
        self.assertEqual(count, 1)

    @patch('subprocess.check_output')
    def test__master_count__error(self, check_output):
        check_output.return_value = "\n"
        check_output.side_effect = subprocess.CalledProcessError(1, '', '')
        with self.assertRaises(subprocess.CalledProcessError):
            pacemaker_is_active.master_resource_expected_count('galera')

    @patch('subprocess.check_output')
    def test__clone__happy_path(self, check_output):
        check_output.return_value = "3\n"
        count = pacemaker_is_active.clone_resource_expected_count('haproxy')
        self.assertEqual(count, 3)

    @patch('modules.pacemaker_is_active._pipe_no_shell')
    @patch('subprocess.check_output')
    def test__clone__catch_error_pre_cp_HA(self, check_output, _pipe_no_shell):
        check_output.side_effect = subprocess.CalledProcessError(6, '', '')
        _pipe_no_shell.side_effect = [["0\n", None], ["\n3\n", None]]
        count = pacemaker_is_active.clone_resource_expected_count('haproxy')
        self.assertEqual(count, 3)

    @patch('modules.pacemaker_is_active._pipe_no_shell')
    @patch('subprocess.check_output')
    def test__clone__catch_error_pre_c_HA2(self, check_output, _pipe_no_shell):
        check_output.side_effect = subprocess.CalledProcessError(6, '', '')
        _pipe_no_shell.return_value = ["2\n", None]
        count = pacemaker_is_active.clone_resource_expected_count('haproxy')
        self.assertEqual(count, 2)

    @patch('subprocess.check_output')
    def test__clone_count__error(self, check_output):
        check_output.return_value = "\n"
        check_output.side_effect = subprocess.CalledProcessError(1, '', '')
        with self.assertRaises(subprocess.CalledProcessError):
            pacemaker_is_active.clone_resource_expected_count('haproxy')


    @patch('subprocess.check_output')
    def test__primitive__stopped(self, check_output):
        xml_string = ''
        with open("./test/units/module/cluster_good.xml", "r") as myfile:
            xml_string = myfile.read()
        check_output.return_value = xml_string
        count = pacemaker_is_active.primitive_resource_expected_count(
            'ip-192.168.24.10'
        )
        self.assertEqual(count, 1)


class TestResourceCurrentCount(unittest.TestCase):
    @patch('subprocess.check_output')
    def test__clone__happy_path(self, check_output):
        xml_string = ''
        with open("./test/units/module/cluster_good.xml", "r") as myfile:
            xml_string = myfile.read()
        check_output.return_value = xml_string
        count = pacemaker_is_active.clone_resource_current_count('haproxy')
        self.assertEqual(count, 3)

    @patch('subprocess.check_output')
    def test__master__happy_path(self, check_output):
        xml_string = ''
        with open("./test/units/module/cluster_good.xml", "r") as myfile:
            xml_string = myfile.read()
        check_output.return_value = xml_string
        count = pacemaker_is_active.master_resource_current_count('galera')
        self.assertEqual(count, 3)

    @patch('subprocess.check_output')
    def test__primitive__happy_path(self, check_output):
        xml_string = ''
        with open("./test/units/module/cluster_good.xml", "r") as myfile:
            xml_string = myfile.read()
        check_output.return_value = xml_string
        count = pacemaker_is_active.primitive_resource_current_count(
            'openstack-cinder-volume')
        self.assertEqual(count, 1)


class TestCloneResource(unittest.TestCase):
    @patch('modules.pacemaker_is_active.clone_resource_current_count')
    @patch('modules.pacemaker_is_active.clone_resource_expected_count')
    @patch('modules.pacemaker_is_active.resource_type_of')
    def test__clone_resource__happy(self,
                                    resource_type_of,
                                    clone_resource_expected_count,
                                    clone_resource_current_count):

        mod_cls = create_autospec(AnsibleModule)
        mod = mod_cls.return_value
        mod.params = dict(
            resource="haproxy",
            max_wait="5"
        )

        resource_type_of.return_value = 'clone'
        clone_resource_expected_count.return_value = 3
        clone_resource_current_count.return_value = 3
        pacemaker_is_active.is_resource_active(mod)
        self.assertEqual(0, mod.fail_json.call_count)
        self.assertEqual(1, mod.exit_json.call_count)

class TestMasterResource(unittest.TestCase):
    @patch('modules.pacemaker_is_active.master_resource_current_count')
    @patch('modules.pacemaker_is_active.master_resource_expected_count')
    @patch('modules.pacemaker_is_active.resource_type_of')
    def test__master_resource__happy(self,
                                     resource_type_of,
                                     master_resource_expected_count,
                                     master_resource_current_count):

        mod_cls = create_autospec(AnsibleModule)
        mod = mod_cls.return_value
        mod.params = dict(
            resource="galera",
            max_wait="5"
        )

        resource_type_of.return_value = 'master'
        master_resource_expected_count.return_value = 3
        master_resource_current_count.return_value = 3
        pacemaker_is_active.is_resource_active(mod)
        self.assertEqual(0, mod.fail_json.call_count)
        self.assertEqual(1, mod.exit_json.call_count)


class TestPrimitiveResource(unittest.TestCase):
    @patch('modules.pacemaker_is_active.primitive_resource_current_count')
    @patch('modules.pacemaker_is_active.resource_type_of')
    def test__primitive_resource__happy(self,
                                        resource_type_of,
                                        primitive_resource_current_count):

        mod_cls = create_autospec(AnsibleModule)
        mod = mod_cls.return_value
        mod.params = dict(
            resource="openstack-cinder-volume",
            max_wait="5"
        )

        resource_type_of.return_value = 'primitive'
        primitive_resource_current_count.return_value = 1
        pacemaker_is_active.is_resource_active(mod)
        self.assertEqual(0, mod.fail_json.call_count)
        self.assertEqual(1, mod.exit_json.call_count)


class TestTimeout(unittest.TestCase):
    @patch('modules.pacemaker_is_active.primitive_resource_current_count')
    @patch('modules.pacemaker_is_active.primitive_resource_expected_count')
    @patch('modules.pacemaker_is_active.resource_type_of')
    def test__primitive_resource__happy(self,
                                        resource_type_of,
                                        primitive_resource_expected_count,
                                        primitive_resource_current_count):

        mod_cls = create_autospec(AnsibleModule)
        mod = mod_cls.return_value
        mod.params = dict(
            resource="openstack-cinder-volume",
            max_wait="3"
        )

        resource_type_of.return_value = 'primitive'
        primitive_resource_expected_count.side_effect = [1, 1, 1]
        primitive_resource_current_count.side_effect = [0, 0, 0]
        pacemaker_is_active.is_resource_active(mod)
        self.assertEqual(1, mod.fail_json.call_count)
        self.assertEqual(0, mod.exit_json.call_count)
