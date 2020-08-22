import datetime
import importlib
import logging
import math
import sys
from typing import Any, Dict, List, Union

import numpy as np
import pandas as pd
import scipy
from redash.query_runner import *
from redash.utils import json_dumps, json_loads
from redash import models
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import guarded_iter_unpack_sequence, guarded_setattr, safe_builtins, safer_getattr


logger = logging.getLogger(__name__)


# Disable reading and writing from/to files using pandas and numpy
def blocked_read_write_func(*args, **kwargs):
    raise RuntimeError("Blocked read/write operation")


pd.io.parsers._read = blocked_read_write_func
for k, v in pd.__dict__.items():
    if k.startswith('read_') and callable(v):
        setattr(pd, k, blocked_read_write_func)
for k, v in pd.core.generic.NDFrame.__dict__.items():
    if k.startswith('to_') and callable(v):
        setattr(pd.core.generic.NDFrame, k, blocked_read_write_func)
for k, v in pd.DataFrame.__dict__.items():
    if k.startswith('to_') and callable(v) and k not in {'to_dict', 'to_numpy', 'to_records'}:
        setattr(pd.DataFrame, k, blocked_read_write_func)
for k, v in pd.Series.__dict__.items():
    if k.startswith('to_') and callable(v) and k not in {'to_dict', 'to_list', 'to_frame', 'to_numpy', 'to_timestamp'}:
        setattr(pd.Series, k, blocked_read_write_func)
for k in ('load', 'loadtxt', 'save', 'savetxt', 'savez', 'savez_compressed', 'genfromtxt', 'fromregex', 'fromfile', 'memmap'):
    setattr(np, k, blocked_read_write_func)


class CustomPrint(object):
    """CustomPrint redirect "print" calls to be sent as "log" on the result object."""

    def __init__(self):
        self.enabled = True
        self.lines = []

    def write(self, text):
        if self.enabled:
            if text and text.strip():
                self.lines.append(text)

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def __call__(self, *args):
         return self

    def _call_print(self, *args, **kwargs):
        print(*args, file=self)


class Python(BaseQueryRunner):
    should_annotate_query = False

    safe_builtins = (
        "sorted",
        "reversed",
        "map",
        "any",
        "all",
        "slice",
        "filter",
        "len",
        "next",
        "enumerate",
        "sum",
        "abs",
        "min",
        "max",
        "round",
        "divmod",
        "str",
        "int",
        "float",
        "complex",
        "tuple",
        "set",
        "list",
        "dict",
        "bool",
        "zip",
        "type",
    )

    @classmethod
    def configuration_schema(cls):
        return {
            "type": "object",
            "properties": {
                "allowedImportModules": {
                    "type": "string",
                    "title": "Modules to import prior to running the script",
                },
                "additionalModulesPaths": {"type": "string"},
            },
        }

    @classmethod
    def enabled(cls):
        return True

    def __init__(self, configuration):
        super(Python, self).__init__(configuration)

        self.syntax = "python"
        self._allowed_modules = {
            "math": math,
            "pandas": pd,
            "numpy": np,
            "scipy": scipy,
        }
        self._enable_print_log = True
        self._custom_print = CustomPrint()

        if self.configuration.get("allowedImportModules", None):
            for item in self.configuration["allowedImportModules"].split(","):
                item = item.strip()
                if item not in self._allowed_modules:
                    self._allowed_modules[item] = None

        if self.configuration.get("additionalModulesPaths", None):
            for p in self.configuration["additionalModulesPaths"].split(","):
                if p not in sys.path:
                    sys.path.append(p)

    def custom_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        if name in self._allowed_modules:
            m = None
            if self._allowed_modules[name] is None:
                m = importlib.import_module(name)
                self._allowed_modules[name] = m
            else:
                m = self._allowed_modules[name]

            return m

        raise Exception(
            "'{0}' is not configured as a supported import module".format(name)
        )

    @staticmethod
    def custom_write(obj):
        """
        Custom hooks which controls the way objects/lists/tuples/dicts behave in
        RestrictedPython
        """
        return obj

    @staticmethod
    def custom_get_item(obj, key):
        return obj[key]

    @staticmethod
    def custom_get_iter(obj):
        return iter(obj)

    @staticmethod
    def get_source_schema(data_source_name_or_id: Union[str, int]):
        """Get schema from specific data source.

        :param data_source_name_or_id: string|integer: Name or ID of the data source
        :return:
        """
        try:
            if type(data_source_name_or_id) == int:
                data_source = models.DataSource.get_by_id(data_source_name_or_id)
            else:
                data_source = models.DataSource.get_by_name(data_source_name_or_id)
        except models.NoResultFound:
            raise Exception("Wrong data source name/id: %s." % data_source_name_or_id)
        schema = data_source.query_runner.get_schema()
        return schema

    @staticmethod
    def execute_query(data_source_name_or_id: Union[str, int], query: str) -> pd.DataFrame:
        """Run query from specific data source.

        Parameters:
        :data_source_name_or_id string|integer: Name or ID of the data source
        :query string: Query to run
        """
        try:
            if type(data_source_name_or_id) == int:
                data_source = models.DataSource.get_by_id(data_source_name_or_id)
            else:
                data_source = models.DataSource.get_by_name(data_source_name_or_id)
        except models.NoResultFound:
            raise Exception("Wrong data source name/id: %s." % data_source_name_or_id)

        # TODO: pass the user here...
        data, error = data_source.query_runner.run_query(query, None)
        if error is not None:
            raise Exception(error)

        # TODO: allow avoiding the JSON dumps/loads in same process
        return Python.df_from_result(json_loads(data))

    @staticmethod
    def get_query_result(query_id: int) -> pd.DataFrame:
        """Get result of an existing query.

        Parameters:
        :query_id integer: ID of existing query
        """
        try:
            query = models.Query.get_by_id(query_id)
        except models.NoResultFound:
            raise Exception("Query id %s does not exist." % query_id)

        if query.latest_query_data is None or query.latest_query_data.data is None:
            raise Exception("Query does not have results yet.")

        return Python.df_from_result(query.latest_query_data.data)

    @staticmethod
    def df_from_result(result: Dict[str, List[Dict[str, Any]]]) -> pd.DataFrame:
        df = pd.DataFrame.from_records(result["rows"])
        column_types = {c["name"]: c["type"] for c in result["columns"]}

        for c in df.columns:
            t = column_types[c]
            if t == TYPE_DATETIME or t == TYPE_DATE:
                df[c] = pd.to_datetime(df[c])
            elif t == TYPE_BOOLEAN:
                df[c] = df[c].astype("boolean")
            elif t == TYPE_INTEGER:
                df[c] = df[c].astype("Int64")
            elif t == TYPE_STRING:
                df[c] = df[c].astype("string")

        return df

    @staticmethod
    def result_from_df(df: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
        df = df.copy()
        columns = []

        for c, t in df.dtypes.iteritems():
            t = str(t).lower()
            column_type = "unknown"
            if t == "object" and df[c].apply(lambda x: isinstance(x, bool) or pd.isna(x)).all():
                df[c] = df[c].astype("boolean")
                column_type = TYPE_BOOLEAN
            elif t == "object" and df[c].apply(lambda x: isinstance(x, datetime.date) or pd.isna(x)).all():
                column_type = TYPE_DATE
            elif t.startswith("int"):
                df[c] = df[c].astype("Int64")
                column_type = TYPE_INTEGER
            elif t.startswith("uint"):
                column_type = TYPE_INTEGER
            elif t.startswith("float") and df[c].apply(lambda x: x.is_integer() or pd.isna(x)).all():
                df[c] = df[c].astype("Int64")
                column_type = TYPE_INTEGER
            elif t.startswith("float"):
                column_type = TYPE_FLOAT
            elif t.startswith("bool"):
                column_type = TYPE_BOOLEAN
            elif t.startswith("datetime"):
                column_type = TYPE_DATETIME
            elif t.startswith("timedelta"):
                df[c] = df[c].dt.total_seconds()
                column_type = TYPE_FLOAT
            elif t.startswith("period"):
                df[c] = df[c].dt.to_timestamp()
                column_type = TYPE_DATETIME
            else:
                df[c] = df[c].apply(lambda x: str(x) if pd.notna(x) else None).astype("string")
                column_type = TYPE_STRING
            columns.append({"name": str(c), "friendly_name": str(c), "type": column_type})

        def convert_value(v: Any) -> Any:
            if pd.isna(v):
                return None
            elif isinstance(v, np.integer):
                return int(v)
            elif isinstance(v, np.floating):
                return float(v)
            elif isinstance(v, np.bool_):
                return bool(v)
            elif isinstance(v, pd.Timestamp):
                return v.to_pydatetime()
            elif isinstance(v, pd.Period):
                return v.to_timestamp().to_pydatetime()
            elif isinstance(v, pd.Interval):
                return str(v)
            return v

        return {
            "columns": columns,
            "rows": [{str(k): convert_value(v) for k, v in r.items()} for r in df.to_dict(orient="records")],
        }

    def get_current_user(self):
        return self._current_user.to_dict()

    def test_connection(self):
        pass

    def run_query(self, query, user):
        self._current_user = user

        try:
            error = None
            code = compile_restricted(query, "<string>", "exec")

            builtins = safe_builtins.copy()
            builtins.update({
                "_write_": self.custom_write,
                "__import__": self.custom_import,
                "_getattr_": safer_getattr,
                "getattr": safer_getattr,
                "_setattr_": guarded_setattr,
                "setattr": guarded_setattr,
                "_getitem_": self.custom_get_item,
                "_getiter_": self.custom_get_iter,
                "_print_": self._custom_print,
                "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            })
            builtins.update({name: __builtins__[name] for name in self.safe_builtins})

            restricted_globals = {
                "__builtins__": builtins,
                "get_query_result": self.get_query_result,
                "get_source_schema": self.get_source_schema,
                "get_current_user": self.get_current_user,
                "execute_query": self.execute_query,

                # Imports
                "math": math,
                "pd": pd,
                "np": np,
                "pandas": pd,
                "numpy": np,
                "scipy": scipy,

                # Prepare empty result
                "result": pd.DataFrame(),
            }

            # TODO: Figure out the best way to have a timeout on a script
            #       One option is to use ETA with Celery + timeouts on workers
            #       And replacement of worker process every X requests handled.

            exec(code, restricted_globals)

            if not isinstance(restricted_globals["result"], pd.DataFrame):
                raise ValueError("result is not a pandas DataFrame")

            result = self.result_from_df(restricted_globals["result"])
            result["log"] = self._custom_print.lines
            json_data = json_dumps(result)
        except Exception as e:
            error = type(e).__name__ + ": " + str(e)
            json_data = None

        return json_data, error


register(Python)
