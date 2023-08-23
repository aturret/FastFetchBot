from typing import Optional, Union
import unittest
import json


class AsyncTestBase(unittest.IsolatedAsyncioTestCase):
    def assert_json(self, first: Union[str, dict], second: Union[str, dict]):
        for json_obj in (first, second):
            if isinstance(json_obj, dict):
                json_dict = json_obj
            elif isinstance(json_obj, str):
                json_dict = json.loads(json_obj)
            else:
                raise TypeError(f"json_str must be str or dict, not {type(json_obj)}")
        self.assertEqual(json_dict, json.loads(json_obj))


class TestBase(unittest.TestCase):
    pass
