from ansible.compat.tests import unittest
from ansible.compat.tests.mock import call, create_autospec, patch
from ansible.module_utils.basic import AnsibleModule

from modules import pacemaker_is_active
import subprocess
import json

GOOD_CIB = "./tests/units/module/cluster_good.xml"


class MyTestUtils(object):
    @staticmethod
    def cib_file_to_string(file_path):
        xml_string = ''
        with open(file_path, "r") as myfile:
            xml_string = myfile.read()
        return xml_string


class TestResourceTypeOf(unittest.TestCase):
    @patch('subprocess.check_output')
    def test__resource_type_of__happy_path(self, check_output):
        check_output.return_value = MyTestUtils.cib_file_to_string(GOOD_CIB)

        expected_result = {
            'haproxy': 'clone',
            'galera': 'master',
            'openstack-cinder-volume': 'primitive',
            'ip-192.168.24.10': 'primitive',
            'blhaaa': None,
        }

        for resource_name, expected_type in expected_result.iteritems():
            found_type = pacemaker_is_active.Resource(
                resource_name
            ).from_type().get_type
            self.assertEqual(found_type, expected_type)


class TestResourceExpectedCount(unittest.TestCase):
    @patch('subprocess.check_output')
    def test__master__happy_path(self, check_output):
        check_output.return_value = "3\n"
        count = pacemaker_is_active.Master(
            'galera'
        ).expected_count()
        self.assertEqual(count, 3)

    @patch('subprocess.check_output')
    def test__master__catch_error(self, check_output):
        check_output.return_value = "\n"
        check_output.side_effect = subprocess.CalledProcessError(6, '', '')
        count = pacemaker_is_active.Master('galera').expected_count()
        self.assertEqual(count, 1)

    @patch('subprocess.check_output')
    def test__master_count__error(self, check_output):
        check_output.return_value = "\n"
        check_output.side_effect = subprocess.CalledProcessError(1, '', '')
        with self.assertRaises(subprocess.CalledProcessError):
            pacemaker_is_active.Master('galera').expected_count()

    @patch('subprocess.check_output')
    def test__clone__happy_path(self, check_output):
        check_output.return_value = "3\n"
        count = pacemaker_is_active.Clone('haproxy').expected_count()
        self.assertEqual(count, 3)

    @patch('modules.pacemaker_is_active.Clone._pipe_no_shell')
    @patch('subprocess.check_output')
    def test__clone__catch_error_pre_cp_HA(self, check_output, _pipe_no_shell):
        check_output.side_effect = subprocess.CalledProcessError(6, '', '')
        _pipe_no_shell.side_effect = [["0\n", None], ["\n3\n", None]]
        count = pacemaker_is_active.Clone('haproxy').expected_count()
        self.assertEqual(count, 3)

    @patch('modules.pacemaker_is_active.Clone._pipe_no_shell')
    @patch('subprocess.check_output')
    def test__clone__catch_error_pre_c_HA2(self, check_output, _pipe_no_shell):
        check_output.side_effect = subprocess.CalledProcessError(6, '', '')
        _pipe_no_shell.return_value = ["2\n", None]
        count = pacemaker_is_active.Clone('haproxy').expected_count()
        self.assertEqual(count, 2)

    @patch('subprocess.check_output')
    def test__clone_count__error(self, check_output):
        check_output.return_value = "\n"
        check_output.side_effect = subprocess.CalledProcessError(1, '', '')
        with self.assertRaises(subprocess.CalledProcessError):
            pacemaker_is_active.Clone('haproxy').expected_count()

    @patch('subprocess.check_output')
    def test__primitive__stopped(self, check_output):
        check_output.return_value = MyTestUtils.cib_file_to_string(GOOD_CIB)
        count = pacemaker_is_active.Primitive(
            'ip-192.168.24.10'
        ).expected_count()
        self.assertEqual(count, 1)


class TestResourceCurrentCount(unittest.TestCase):
    @patch('subprocess.check_output')
    def test__clone__happy_path(self, check_output):
        check_output.return_value = MyTestUtils.cib_file_to_string(GOOD_CIB)
        count = pacemaker_is_active.Clone('haproxy').current_count()
        self.assertEqual(count, 3)

    @patch('subprocess.check_output')
    def test__master__happy_path(self, check_output):
        check_output.return_value = MyTestUtils.cib_file_to_string(GOOD_CIB)
        count = pacemaker_is_active.Master('galera').current_count()
        self.assertEqual(count, 3)

    @patch('subprocess.check_output')
    def test__primitive__happy_path(self, check_output):
        check_output.return_value = MyTestUtils.cib_file_to_string(GOOD_CIB)
        count = pacemaker_is_active.Primitive(
            'openstack-cinder-volume'
        ).current_count()
        self.assertEqual(count, 1)


class TestCloneResource(unittest.TestCase):
    @patch('modules.pacemaker_is_active.Clone.current_count')
    @patch('modules.pacemaker_is_active.Clone.expected_count')
    @patch('modules.pacemaker_is_active.Resource.from_type')
    def test__clone_resource__happy(self,
                                    has_type,
                                    clone_resource_expected_count,
                                    clone_resource_current_count):

        mod_cls = create_autospec(AnsibleModule)
        mod = mod_cls.return_value
        mod.params = dict(
            resource="haproxy",
            max_wait="5"
        )

        has_type.return_value = pacemaker_is_active.Clone('haproxy')
        clone_resource_expected_count.return_value = 3
        clone_resource_current_count.return_value = 3
        pacemaker_is_active.is_resource_active(mod)
        self.assertEqual(0, mod.fail_json.call_count)
        self.assertEqual(1, mod.exit_json.call_count)


class TestMasterResource(unittest.TestCase):
    @patch('modules.pacemaker_is_active.Master.current_count')
    @patch('modules.pacemaker_is_active.Master.expected_count')
    @patch('modules.pacemaker_is_active.Resource.from_type')
    def test__master_resource__happy(self,
                                     has_type,
                                     master_resource_expected_count,
                                     master_resource_current_count):

        mod_cls = create_autospec(AnsibleModule)
        mod = mod_cls.return_value
        mod.params = dict(
            resource="galera",
            max_wait="5"
        )

        has_type.return_value = pacemaker_is_active.Master('galera')
        master_resource_expected_count.return_value = 3
        master_resource_current_count.return_value = 3
        pacemaker_is_active.is_resource_active(mod)
        self.assertEqual(0, mod.fail_json.call_count)
        self.assertEqual(1, mod.exit_json.call_count)


class TestPrimitiveResource(unittest.TestCase):
    @patch('modules.pacemaker_is_active.Primitive.current_count')
    @patch('modules.pacemaker_is_active.Resource.from_type')
    def test__primitive_resource__happy(self,
                                        has_type,
                                        primitive_resource_current_count):

        mod_cls = create_autospec(AnsibleModule)
        mod = mod_cls.return_value
        mod.params = dict(
            resource="openstack-cinder-volume",
            max_wait="5"
        )

        has_type.return_value = pacemaker_is_active.Primitive(
            "openstack-cinder-volume")
        primitive_resource_current_count.return_value = 1
        pacemaker_is_active.is_resource_active(mod)
        self.assertEqual(0, mod.fail_json.call_count)
        self.assertEqual(1, mod.exit_json.call_count)


class TestTimeout(unittest.TestCase):
    @patch('modules.pacemaker_is_active.Primitive.current_count')
    @patch('modules.pacemaker_is_active.Primitive.expected_count')
    @patch('modules.pacemaker_is_active.Resource.from_type')
    def test__primitive_resource__happy(self,
                                        has_type,
                                        primitive_resource_expected_count,
                                        primitive_resource_current_count):

        mod_cls = create_autospec(AnsibleModule)
        mod = mod_cls.return_value
        mod.params = dict(
            resource="openstack-cinder-volume",
            max_wait="3"
        )

        has_type.return_value = pacemaker_is_active.Primitive(
            'openstack-cinder-volume')
        primitive_resource_expected_count.side_effect = [1, 1, 1]
        primitive_resource_current_count.side_effect = [0, 0, 0]
        pacemaker_is_active.is_resource_active(mod)
        self.assertEqual(1, mod.fail_json.call_count)
        self.assertEqual(0, mod.exit_json.call_count)
