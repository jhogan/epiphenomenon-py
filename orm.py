# vim: set et ts=4 sw=4 fdm=marker
"""
MIT License

Copyright (c) 2018 Jesse Hogan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from pdb import set_trace; B=set_trace
from pprint import pprint
from table import table
import builtins
import textwrap
from uuid import uuid4
import entities
import sys

class undef:
    pass

class epiphany:
    pass

class entitymeta(type):
    def __new__(cls, name, bases, body):
        return super().__new__(cls, name, bases, body)

class entity(entities.entity, metaclass=entitymeta):
    def __init__(self):
        self.epiphany = epiphany()
        # The code:
        #
        #     self.epiphany.mappings = mappings()
        #
        # raises UnboundLocalError for some reason. The local variable
        # 'mappings' below seems to be causing the problem.
        self.epiphany.mappings = sys.modules[__name__].mappings()

        try:
            mappings = self.getmappings()
        except Exception as ex:
            msg = 'orm entities must implement a static getmappings method'
            raise NotImplementedError(msg)

        if mappings:
            for mapping in mappings:
                self.epiphany.mappings += mapping

        self._id = uuid4()

        super().__init__()
    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, v):
        self._id = v
        return self._id

    def __dir__(self):
        return super().__dir__() + [x.name for x in self.epiphany.mappings]

    def __setattr__(self, attr, v):
        # Need to handle 'epiphany' first, otherwise the code below that
        # calls self.epiphany won't work.
        if attr == 'epiphany':
            return object.__setattr__(self, attr, v)

        map = self.epiphany.mappings[attr]

        if map is None:
            return object.__setattr__(self, attr, v)
        else:
            # Call entity._setvalue to take advantage of its event raising
            # code. Pass in a custom setattr function for it to call. Use
            # underscores for the paramenters since we already have the values
            # it would pass in in this method's scope - execpt for the v
            # which, may have been processed (i.e, if it is a str, it will
            # have been strip()ed. 
            def setattr(_, __, v):
                map.value = v

            self._setvalue(attr, v, attr, setattr)

    @property
    def brokenrules(self):
        brs = entities.brokenrules()
        for map in self.epiphany.mappings:

            if map.type == str:
                if map.max is undef:
                    if map.value is not None:
                        brs.demand(self, map.name, max=255)
                else:
                    brs.demand(self, map.name, max=map.max)

                if map.full:
                    brs.demand(self, map.name, full=True)
                        
        return brs

    def __getattribute__(self, attr):
        map = None

        if attr != 'epiphany':
            map = self.epiphany.mappings[attr]

        if map is None:
            return object.__getattribute__(self, attr)

        return map.value

class mappings(entities.entities):
    pass

class mapping(entities.entity):
    def __init__(self, name, type, default=undef, max=undef, full=False):
        self._name = name
        self._type = type
        self._value = undef
        self._default = default
        self._max = max
        self._full = full

    @property
    def full(self):
        return self._full

    @property
    def default(self):
        return self._default

    @property
    def max(self):
        return self._max

    @property
    def type(self):
        return self._type

    @property
    def name(self):
        return self._name

    @property
    def value(self):
        if self._value is undef:
            if self.default is undef:
                if self.type == builtins.str:
                    return ''
            else:
                return self.default
        else:
            return self._value

    @value.setter
    def value(self, v):
        self._value = v



