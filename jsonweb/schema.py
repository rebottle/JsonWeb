# noinspection PyUnresolvedReferences
"""
:mod:`jsonweb.schema` provides a layer of validation before :mod:`json.decode`
returns your object instances. It can also be used simply to validate the
resulting python data structures returned from :func:`json.loads`. Here is an
example of validating the structure of a python dict::

    >>>
    >>> from jsonweb.schema import ObjectSchema, ValidationError
    >>> from jsonweb.validators import String

    >>> class PersonSchema(ObjectSchema):
    ...     first_name = String()
    ...     last_name = String()

    >>> try:
    ...     PersonSchema().validate({"first_name": "shawn"})
    ... except ValidationError, e:
    ...     print e.errors
    {"last_name": "Missing required parameter."}

Validating plain old python data structures is fine, but the more interesting
exercise is tying a schema to a class definition::

    >>> from jsonweb.decode import from_object, loader
    >>> from jsonweb.schema import ObjectSchema, ValidationError
    >>> from jsonweb.validators import String, Integer, EnsureType

    >>> class PersonSchema(ObjectSchema):
    ...    id = Integer()
    ...    first_name = String()
    ...    last_name = String()
    ...    gender = String(optional=True)
    ...    job = EnsureType("Job")

You can make any field optional by setting ``optional`` to :class:`True`.

.. warning::

    The field is only optional at the schema level. If you've bound a schema to
    a class via :func:`from_object` and the underlying class requires that field
    a :class:`ObjectAttributeError` will be raised if missing.

As you can see its fine to pass a class name as a string, which we have done for
the :class:`Job` class above. We must later define :class:`Job` and decorate it
with :func:`jsonweb.decode.from_object` ::

    >>> class JobSchema(ObjectSchema):
    ...    id = Integer()
    ...    title = String()

    >>> @from_object(schema=JobSchema)
    ... class Job(object):
    ...     def __init__(self, id, title):
    ...         self.id = id
    ...         self.title = title

    >>> @from_object(schema=PersonSchema)
    ... class Person(object):
    ...     def __init__(self, first_name, last_name, job, gender=None):
    ...         self.first_name = first_name
    ...         self.last_name = last_name
    ...         self.gender = gender
    ...         self.job = job
    ...     def __str__(self):
    ...         return '<Person name="%s" job="{0}">'.format(
    ...             " ".join((self.first_name, self.last_name)),
    ...             self.job.title
    ...         )

    >>> person_json = '''
    ...     {
    ...         "__type__": "Person",
    ...         "id": 1,
    ...         "first_name": "Bob",
    ...         "last_name": "Smith",
    ...         "job": {"__type__": "Job", "id": 5, "title": "Police Officer"},
    ...     }'''
    ...

    >>> person = loader(person_json)
    >>> print person
    <Person name="Bob" job="Police Officer">
"""

from jsonweb.py3k import PY3k, items
from jsonweb.validators import BaseValidator, _Errors, \
    ValidationError, isinstance_or_raise


class SchemaMeta(type):
    def __new__(mcs, class_name, bases, class_dict):
        fields = []
        for k, v in items(class_dict):
            if hasattr(v, "_validate"):
                fields.append(k)
        class_dict["_fields"] = fields
        return type.__new__(mcs, class_name, bases, class_dict)


class ObjectSchema(BaseValidator):
    __metaclass__ = SchemaMeta

    def to_json(self):
        return super(ObjectSchema, self).to_json(
            fields=dict([(f, getattr(self, f)) for f in self._fields])
        )

    def _validate(self, obj):
        isinstance_or_raise(obj, dict)
        val_obj = {}
        errors = _Errors({})

        for field in self._fields:
            v = getattr(self, field)
            try:
                if field not in obj:
                    if v.default is not None:
                        val_obj[field] = v.default
                    elif v.required:
                        errors.add_error(
                            "Missing required parameter.",
                            key=field,
                            error_type="required_but_missing"
                        )
                else:
                    val_obj[field] = v.validate(obj[field])
            except ValidationError as e:
                errors.add_error(e, key=field)

        errors.raise_if_errors("Error validating object.",
                               error_type="invalid_object")
        return val_obj


def bind_schema(type_name, schema_obj):
    """
    Use this function to add an :class:`ObjectSchema` to a class already
    decorated by :func:`from_object`.
    """
    from jsonweb.decode import _default_object_handlers
    _default_object_handlers._update_handler_deferred(type_name,
                                                      schema=schema_obj)

if PY3k:
    ObjectSchema = SchemaMeta(
        ObjectSchema.__name__,
        (BaseValidator, ),
        dict(vars(ObjectSchema))
    )