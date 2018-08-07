import os
import unittest
import tempfile

import mock

import bd.hooks
from bd.exceptions import *


class bd_hooks_registry_TestCase(unittest.TestCase):

    def test_get_hooks_sorting(self):
        registry = bd.hooks.HookRegistry()
        registry.add_hook("hook_1", lambda: "hook_1_callback")
        registry.add_hook("hook_1", lambda: "hook_2_callback")

        self.assertEqual(len(registry.get_hooks("hook_1")), 2)
        self.assertEqual(registry.get_hooks("hook_1")[0][1](), "hook_1_callback")

    def test_adding_solo_hook_multiple_times(self):
        registry = bd.hooks.HookRegistry()

        registry.add_hook("hook_1", lambda: "callback_1", force_solo=True)
        registry.add_hook("hook_1", lambda: "callback_2")

        self.assertEqual(len(registry.get_hooks("hook_1")), 1)

        _, callback, obj_weakref = registry.get_hooks("hook_1")[0]
        self.assertEqual(callback(), "callback_1")

        registry = bd.hooks.HookRegistry()

        registry.add_hook("hook_1", lambda: "callback_1")
        registry.add_hook("hook_1", lambda: "callback_2", force_solo=True)

        self.assertEqual(len(registry.get_hooks("hook_1")), 1)

        _, callback, obj_weakref = registry.get_hooks("hook_1")[0]
        self.assertEqual(callback(), "callback_2")

    def test_adding_normal_hook_multiple_times(self):
        registry = bd.hooks.HookRegistry()

        registry.add_hook("hook_1", lambda: "callback_1")
        registry.add_hook("hook_1", lambda: "callback_2")

        self.assertEqual(len(registry.get_hooks("hook_1")), 2)

        hook_infos = registry.get_hooks("hook_1")

        _, callback, obj_weakref = hook_infos[0]
        self.assertEqual(callback(), "callback_1")

        _, callback, obj_weakref = hook_infos[1]
        self.assertEqual(callback(), "callback_2")

    def test_adding_function_and_method_hooks(self):
        registry = bd.hooks.HookRegistry()

        class TestClass(object):
            def method(self):
                return "method_hook"

        test_obj = TestClass()

        registry.add_hook("hook_1", test_obj.method)

        self.assertEqual(len(registry.get_hooks("hook_1")), 1)

        hook_infos = registry.get_hooks("hook_1")

        _, callback, obj_weakref = hook_infos[0]

        self.assertIsNotNone(obj_weakref)

        self.assertEqual(callback(obj_weakref()), "method_hook")

        registry.add_hook("hook_2", lambda: "function_hook")

        hook_infos = registry.get_hooks("hook_2")

        self.assertEqual(len(registry.get_hooks("hook_2")), 1)

        _, callback, obj_weakref = hook_infos[0]

        self.assertIsNone(obj_weakref)

        self.assertEqual(callback(), "function_hook")

    def test_priority(self):
        registry = bd.hooks.HookRegistry()

        registry.add_hook("hook_1", lambda: "callback_1", priority=40)
        registry.add_hook("hook_1", lambda: "callback_2", priority=80)

        hook_infos = registry.get_hooks("hook_1")

        _, callback, obj_weakref = hook_infos[0]
        self.assertEqual(callback(), "callback_2")

        _, callback, obj_weakref = hook_infos[1]
        self.assertEqual(callback(), "callback_1")

    def test_invalid_callback(self):
        registry = bd.hooks.HookRegistry()
        self.assertRaises(InvalidCallbackError, registry.add_hook, "hook_1", "")

    def test_hook_does_not_exist(self):
        registry = bd.hooks.HookRegistry()
        self.assertRaises(HookNotFoundError, registry.get_hooks, "hook_1")

    def test_dead_weakref(self):
        registry = bd.hooks.HookRegistry()

        class TestClass(object):
            def method(self):
                return "method_hook"

        # add one method from one object and delete it

        test_object = TestClass()

        registry.add_hook("hook_1", test_object.method)

        del test_object

        self.assertRaises(HookCallbackDeadError, registry.get_hooks, "hook_1")

        self.assertNotIn("hook_1", registry._hooks)
        self.assertEqual(len(registry._hooks), 0)

        self.assertNotIn("hook_1", registry._sorted)
        self.assertEqual(len(registry._sorted), 0)

        self.assertNotIn("hook_1", registry._forced_solo)
        self.assertEqual(len(registry._forced_solo), 0)

        # adding multiple methods and sequentially deleting them

        test_object_1 = TestClass()
        test_object_2 = TestClass()

        registry.add_hook("hook_1", test_object_1.method)
        registry.add_hook("hook_1", test_object_2.method)

        del test_object_1

        self.assertEqual(len(registry.get_hooks("hook_1")), 1)

        _, _, obj_weakref = registry.get_hooks("hook_1")[0]

        self.assertIs(obj_weakref(), test_object_2)

        del test_object_2

        self.assertRaises(HookCallbackDeadError, registry.get_hooks, "hook_1")

        self.assertNotIn("hook_1", registry._hooks)
        self.assertEqual(len(registry._hooks), 0)

        self.assertNotIn("hook_1", registry._sorted)
        self.assertEqual(len(registry._sorted), 0)

        self.assertNotIn("hook_1", registry._forced_solo)
        self.assertEqual(len(registry._forced_solo), 0)

    def test_classmethod(self):
        registry = bd.hooks.HookRegistry()

        class TestClass(object):
            @classmethod
            def method(self):
                return "classmethod"

        registry.add_hook("hook_1", TestClass.method)

        self.assertEqual(len(registry.get_hooks("hook_1")), 1)

        _, callback, obj_weakref = registry.get_hooks("hook_1")[0]

        self.assertIsNotNone(obj_weakref())
        self.assertEqual(callback(obj_weakref()), "classmethod")


class bd_hooks_loader_TestCase(unittest.TestCase):

    def test_load_with_no_search_paths_defined(self):
        with mock.patch.dict("os.environ"):
            os.environ.pop("BD_HOOKPATH", None)
            self.assertRaises(SearchPathsNotDefinedError, bd.hooks.loader.HookLoader.load, None)

    def test_load_if_no_hooks_found(self):
        self.assertIsNone(bd.hooks.loader.HookLoader.load(None, [tempfile.gettempdir()]))
        self.assertIsNone(bd.hooks.loader.HookLoader._plugin_source)

    @mock.patch("bd.hooks.loader.PluginBase")
    @mock.patch("bd.hooks.loader.get_searchpath")
    def test_if_hook_failures(self, mock_get_searchpath, mock_pluginbase):
        mock_get_searchpath.return_value = ["asdasd"]
        mock_plugin_source = mock.Mock()
        mock_pluginbase.return_value.make_plugin_source.return_value = mock_plugin_source
        mock_plugin_source.list_plugins.return_value = ["1"]
        mock_plugin_source.load_plugin.side_effect = Exception()
        self.assertRaises(HookLoadingError, bd.hooks.loader.HookLoader.load, None, [tempfile.gettempdir()])
        bd.hooks.loader.HookLoader.clean()

        mock_plugin_source.load_plugin.side_effect = None
        mock_plugin = mock.Mock()
        mock_plugin_source.load_plugin.return_value = mock_plugin
        mock_plugin.register.side_effect = Exception()
        self.assertRaises(HookRegistrationError, bd.hooks.loader.HookLoader.load, None, [tempfile.gettempdir()])
        bd.hooks.loader.HookLoader.clean()


class bd_hooks_executor_TestCase(unittest.TestCase):

    def test_execute_one_if_get_hooks_failed(self):
        mock_registry = mock.Mock()
        mock_registry.get_hooks.side_effect = Exception()
        executor = bd.hooks.executor.HookExecutor(mock_registry, "hook_1")
        self.assertRaises(Exception, executor.one)

    def test_execute_all_if_get_hooks_failed(self):
        mock_registry = mock.Mock()
        mock_registry.get_hooks.side_effect = Exception()
        executor = bd.hooks.executor.HookExecutor(mock_registry, "hook_1")
        self.assertRaises(Exception, executor.all)

    def test_exec_single(self):
        mock_registry = mock.Mock()
        mock_registry.get_hooks.side_effect = Exception()
        executor = bd.hooks.executor.HookExecutor(mock_registry, "hook_1")
        mock_callback = mock.Mock()
        mock_callback.side_effect = Exception()
        self.assertRaises(CallbackExecutionError, executor._exec_single, (50, mock_callback, None))

    def test_one(self):
        registry = bd.hooks.registry.HookRegistry()
        registry.add_hook("hook_1", lambda: "hook_1_callback", 50)
        registry.add_hook("hook_1", lambda: "hook_2_callback", 50)

        executor = bd.hooks.executor.HookExecutor(registry, "hook_1")
        self.assertEqual(executor.one(), "hook_1_callback")

    def test_one_with_sorting(self):
        registry = bd.hooks.registry.HookRegistry()
        registry.add_hook("hook_1", lambda: "hook_1_callback", 50)
        registry.add_hook("hook_1", lambda: "hook_2_callback", 60)

        executor = bd.hooks.executor.HookExecutor(registry, "hook_1")
        self.assertEqual(executor.one(), "hook_2_callback")

    def test_all(self):
        registry = bd.hooks.registry.HookRegistry()
        registry.add_hook("hook_1", lambda: "hook_1_callback", 50)
        registry.add_hook("hook_1", lambda: "hook_2_callback", 50)
        executor = bd.hooks.executor.HookExecutor(registry, "hook_1")

        results = []
        result_callback = lambda x: results.append(x)

        executor.all(result_callback)

        self.assertListEqual(results, ["hook_1_callback", "hook_2_callback"])

    def test_all_with_sorting(self):
        registry = bd.hooks.registry.HookRegistry()
        registry.add_hook("hook_1", lambda: "hook_1_callback", 50)
        registry.add_hook("hook_1", lambda: "hook_2_callback", 60)
        executor = bd.hooks.executor.HookExecutor(registry, "hook_1")

        results = []
        result_callback = lambda x: results.append(x)

        executor.all(result_callback)

        self.assertListEqual(results, ["hook_2_callback", "hook_1_callback"])


if __name__ == '__main__':
    unittest.main()