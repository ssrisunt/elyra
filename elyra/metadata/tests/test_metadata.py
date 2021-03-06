#
# Copyright 2018-2020 IBM Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import copy
import json
import os
import shutil
import pytest

from jsonschema import validate, ValidationError, draft7_format_checker
from elyra.metadata import Metadata, MetadataManager, SchemaManager, METADATA_TEST_NAMESPACE
from .test_utils import valid_metadata_json, invalid_metadata_json, create_json_file, get_schema


os.environ["METADATA_TESTING"] = "1"  # Enable metadata-tests namespace

# Test factory schemas.
# Note: should we ever decide to allow folks to bring their own schemas, we'd want to expose this.
schema_schema = {
    "title": "Schema for Elyra schema.",
    "properties": {
        "name": {
            "description": "The name of the schema.",
            "type": "string",
            "pattern": "^[a-z][a-z0-9-_]*[a-z0-9]$"
        },
        "namespace": {
            "description": "The namespace corresponding to the schema and its instances.",
            "type": "string",
            "pattern": "^[a-z][a-z0-9-_]*[a-z0-9]$"
        },
        "properties": {
            "type": "object",
            "propertyNames": {
                "enum": ["schema_name", "display_name", "metadata"]
            },
            "additionalProperties": True
        }
    },
    "required": ["name", "namespace", "properties"]
}


def test_validate_factory_schemas():
    # Test that each of our factory schemas meet the minimum requirements.
    namespace_schemas = SchemaManager.load_namespace_schemas()
    for namespace, schemas in namespace_schemas.items():
        for name, schema in schemas.items():
            print("Validating schema '{namespace}/{name}'...".format(namespace=namespace, name=name))
            validate(instance=schema, schema=schema_schema, format_checker=draft7_format_checker)


# ########################## MetadataManager Tests ###########################
def test_manager_add_invalid(tests_manager, data_dir):

    with pytest.raises(ValueError):
        MetadataManager(namespace='invalid')

    # Attempt with non Metadata instance
    with pytest.raises(TypeError):
        tests_manager.add(invalid_metadata_json)

    # and invalid parameters
    with pytest.raises(ValueError):
        tests_manager.add(None, invalid_metadata_json)

    with pytest.raises(ValueError):
        tests_manager.add("foo", None)


def test_manager_list_summary(tests_manager):
    metadata_summary_list = tests_manager.get_all_metadata_summary(include_invalid=False)
    assert len(metadata_summary_list) == 2
    metadata_summary_list = tests_manager.get_all_metadata_summary(include_invalid=True)
    assert len(metadata_summary_list) == 3


def test_manager_list_all(tests_manager):
    metadata_list = tests_manager.get_all()
    assert len(metadata_list) == 2
    # Ensure name is getting derived from resource and not from contents
    for metadata in metadata_list:
        if metadata.display_name == "Another Metadata Instance (2)":
            assert metadata.name == "another"
        else:
            assert metadata.name == "valid"


def test_manager_list_summary_none(tests_manager, metadata_tests_dir):
    # Delete the metadata dir contents and attempt listing metadata
    shutil.rmtree(metadata_tests_dir)
    assert tests_manager.namespace_exists() is False
    os.makedirs(metadata_tests_dir)
    assert tests_manager.namespace_exists()

    metadata_summary_list = tests_manager.get_all_metadata_summary()
    assert len(metadata_summary_list) == 0


def test_manager_list_all_none(tests_manager, metadata_tests_dir):
    # Delete the metadata dir contents and attempt listing metadata
    shutil.rmtree(metadata_tests_dir)
    assert tests_manager.namespace_exists() is False
    os.makedirs(metadata_tests_dir)
    assert tests_manager.namespace_exists()

    metadata_list = tests_manager.get_all()
    assert len(metadata_list) == 0


def test_manager_add_remove_valid(tests_manager, metadata_tests_dir):
    metadata_name = 'valid_add_remove'

    metadata = Metadata(**valid_metadata_json)

    resource = tests_manager.add(metadata_name, metadata)
    assert resource is not None

    # Ensure file was created
    metadata_file = os.path.join(metadata_tests_dir, 'valid_add_remove.json')
    assert os.path.exists(metadata_file)

    with open(metadata_file, 'r', encoding='utf-8') as f:
        valid_add = json.loads(f.read())
        assert "resource" not in valid_add
        assert "name" not in valid_add
        assert "display_name" in valid_add
        assert valid_add['display_name'] == "valid metadata instance"
        assert "schema_name" in valid_add
        assert valid_add['schema_name'] == "metadata-test"

    # Attempt to create again w/o replace, then replace it.
    resource = tests_manager.add(metadata_name, metadata, replace=False)
    assert resource is None

    resource = tests_manager.add(metadata_name, metadata)
    assert resource is not None

    # And finally, remove it.
    resource = tests_manager.remove(metadata_name)

    assert not os.path.exists(metadata_file)
    assert resource == metadata_file


def test_manager_remove_invalid(tests_manager, metadata_tests_dir):
    # Ensure invalid metadata file isn't validated and is removed.
    create_json_file(metadata_tests_dir, 'remove_invalid.json', invalid_metadata_json)
    metadata_name = 'remove_invalid'
    resource = tests_manager.remove(metadata_name)
    metadata_file = os.path.join(metadata_tests_dir, 'remove_invalid.json')
    assert not os.path.exists(metadata_file)
    assert resource == metadata_file


def test_manager_remove_missing(tests_manager, metadata_tests_dir):
    # Ensure removal of missing metadata file is handled.
    metadata_name = 'missing'
    resource = tests_manager.remove(metadata_name)
    assert resource is None


def test_manager_read_valid_by_name(tests_manager, metadata_tests_dir):
    metadata_name = 'valid'
    some_metadata = tests_manager.get(metadata_name)
    assert some_metadata.name == metadata_name
    assert some_metadata.schema_name == "metadata-test"
    assert str(metadata_tests_dir) in some_metadata.resource


def test_manager_read_invalid_by_name(tests_manager):
    metadata_name = 'invalid'
    with pytest.raises(ValidationError):
        tests_manager.get(metadata_name)


def test_manager_read_missing_by_name(tests_manager):
    metadata_name = 'missing'
    with pytest.raises(KeyError):
        tests_manager.get(metadata_name)


# ########################## FileMetadataStore Tests ###########################
def test_filestore_list_summary(filestore):
    metadata_summary_list = filestore.get_all_metadata_summary(include_invalid=False)
    assert len(metadata_summary_list) == 2
    metadata_summary_list = filestore.get_all_metadata_summary(include_invalid=True)
    assert len(metadata_summary_list) == 3


def test_filestore_list_all(filestore):
    metadata_list = filestore.get_all()
    assert len(metadata_list) == 2


def test_filestore_list_summary_none(filestore, metadata_tests_dir):
    # Delete the metadata dir contents and attempt listing metadata
    shutil.rmtree(metadata_tests_dir)
    assert filestore.namespace_exists() is False
    os.makedirs(metadata_tests_dir)
    assert filestore.namespace_exists()

    metadata_summary_list = filestore.get_all_metadata_summary(include_invalid=True)
    assert len(metadata_summary_list) == 0


def test_filestore_list_all_none(filestore, metadata_tests_dir):
    # Delete the metadata dir contents and attempt listing metadata
    shutil.rmtree(metadata_tests_dir)
    assert filestore.namespace_exists() is False
    os.makedirs(metadata_tests_dir)
    assert filestore.namespace_exists()

    metadata_list = filestore.get_all()
    assert len(metadata_list) == 0


def test_filestore_read_valid_by_name(filestore):
    metadata_name = 'valid'
    some_metadata = filestore.read(metadata_name)
    assert some_metadata.name == metadata_name


def test_filestore_read_invalid_by_name(filestore):
    metadata_name = 'invalid'
    with pytest.raises(ValidationError):
        filestore.read(metadata_name)


def test_filestore_read_missing_by_name(filestore):
    metadata_name = 'missing'
    with pytest.raises(KeyError):
        filestore.read(metadata_name)


# ########################## SchemaManager Tests ###########################
def test_schema_manager_all(schema_manager):
    schema_manager.clear_all()

    test_schema_json = get_schema('metadata-test')

    with pytest.raises(ValueError):
        schema_manager.add_schema("foo", "metadata-test", test_schema_json)

    with pytest.raises(ValueError):
        schema_manager.add_schema("bar", "metadata-test", test_schema_json)

    schema_manager.add_schema(METADATA_TEST_NAMESPACE, "metadata-test", test_schema_json)

    test_schema = schema_manager.get_schema(METADATA_TEST_NAMESPACE, "metadata-test")
    assert test_schema is not None
    assert test_schema == test_schema_json

    # extend the schema... add and ensure update exists...
    modified_schema = copy.deepcopy(test_schema)
    modified_schema['properties']['metadata']['properties']['bar'] = {"type": "string", "minLength": 5}

    schema_manager.add_schema(METADATA_TEST_NAMESPACE, "metadata-test", modified_schema)
    bar_schema = schema_manager.get_schema(METADATA_TEST_NAMESPACE, "metadata-test")
    assert bar_schema is not None
    assert bar_schema != test_schema_json
    assert bar_schema == modified_schema

    schema_manager.remove_schema(METADATA_TEST_NAMESPACE, "metadata-test")
    with pytest.raises(KeyError):
        schema_manager.get_schema(METADATA_TEST_NAMESPACE, "metadata-test")

    schema_manager.clear_all()  # Ensure test schema has been restored
    test_schema = schema_manager.get_schema(METADATA_TEST_NAMESPACE, "metadata-test")
    assert test_schema is not None
    assert test_schema == test_schema_json
