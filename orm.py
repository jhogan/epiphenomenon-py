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
from pprint import pprint
from table import table
import builtins
import textwrap
from uuid import uuid4, UUID
import entities as entitiesmod
import sys
import db
from MySQLdb.constants.ER import BAD_TABLE_ERROR
import MySQLdb
from enum import Enum, unique
import re
import primative
import dateutil
import decimal
from datetime import datetime
import gc
from shlex import shlex

# Set conditional break points
def B(x=True):
    if type(x) is str:
        print(x)
    elif x:
        #Pdb().set_trace(sys._getframe().f_back)
        from IPython.core.debugger import Tracer; 
        Tracer().debugger.set_trace(sys._getframe().f_back)

# TODO Research making these constants the same as their function equivilants,
# i.e., s/2/str; s/3/int/, etc.
@unique
class types(Enum):
    pk        =  0
    fk        =  1
    str       =  2
    int       =  3
    datetime  =  4
    bool      =  5
    float     =  6
    decimal   =  7
    bytes     =  8

class undef:
    pass

class stream(entitiesmod.entity):
    def __init__(self, chunksize=100):
        self.cursor = self.cursor(self)
        self.chunksize = chunksize
        self.orderby = ''

    class cursor(entitiesmod.entity):
        def __init__(self, stm, start=0, stop=0):
            self.stream = stm
            self._chunk = None
            self._start = start
            self._stop = stop
            self.chunkloaded = False

        def __repr__(self):
            r = type(self).__name__ + ': '
            for prop in 'start', 'stop', 'limit', 'size', 'offset':
                r += '%s=%s ' % (prop, str(getattr(self, prop)))
            return r
        
        @property
        def chunk(self):
            if self._chunk is None:
                where = self.entities.orm.where
                cond = where.conditional
                args = where.args
                self._chunk = type(self.entities)(cond, args)
                self._chunk.orm.ischunk = True

            return self._chunk

        @property
        def entities(self):
            return self.stream.entities

        def __contains__(self, slc):
            slc = self.normalizedslice(slc)
            return self.start <= slc.start and \
                   self.stop  >= slc.stop

        def advance(self, slc):
            if isinstance(slc, int):
                slc = slice(slc, slc + 1)

            if slc.start is None:
                slc = slice(int(), slc.stop)

            if slc.stop is None:
                slc = slice(slc.stop, int())

            # Return an empty collection if start >= stop
            if slc.start >= slc.stop:
                if slc.stop < 0:
                    # TODO es[3:3] or es[3:2] will produce empty results like
                    # lists do. However, es[3:-1] should produces a non-empty
                    # result (also like lists). However, this case is currently
                    # not implemented at the moment.
                    msg = 'Negative stops not implemented'
                    raise NotImplementedError(msg)
                return self.chunk[0:0]

            if slc not in self or not self.chunkloaded:
                self._start = slc.start
                self._stop = slc.stop

                self.chunk.clear()
                self.chunk.load(self.stream.orderby, self.limit, self.offset)
                self.chunkloaded = True

            return self.chunk[self.getrelativeslice(slc)]

        def __iter__(self):
            # TODO To make this object a proper iterable, shouldn't we override
            # the __next__()
            slc= slice(0, self.stream.chunksize)
            self.advance(slc)
            yield self.chunk

            while True:
                size = self.stream.chunksize
                slc = slice(slc.start + size, slc.stop + size)

                if slc.start >= self.entities.count:
                    raise StopIteration()

                gc.collect()
                yield self.advance(slc)

        def getrelativeslice(self, slc):
            slc = self.normalizedslice(slc)
            
            start = slc.start - self.offset
            stop  = slc.stop  - self.offset
            return slice(start, stop)

        def normalizedslice(self, slc):
            # Normalize negatives
            cnt = self.stream.entities.count   

            if slc.start < 0:
                slc = slice(slc.start + cnt, slc.stop)

            if slc.stop <= 0:
                slc = slice(slc.start, slc.stop + cnt)

            return slc
            
        @property
        def start(self):
            # I.e., offset
            start = self._start

            # Deal with negatives
            if start < 0:
                start += self.stream.entities.count

            return start

        @property
        def stop(self):
            if self._stop < 0:
                self._stop += self.stream.entities.count

            if self.stream.chunksize < self._stop - self.start:
                self._stop = self._stop
            else:
                self._stop = self.start + self.stream.chunksize

            return self._stop

        @property
        def size(self):
            # I.e., 'limit'
            return self.stop - self.start 

        @property
        def limit(self):
            return self.size

        @property
        def offset(self):
            return self.start

class joins(entitiesmod.entities):
    def __init__(self, initial=None, es=None):
        if es is None:
            raise ValueError('Missing entities')
        self.entities = es
        super().__init__(initial=initial)

    @property
    def table(self):
        return self.entities.orm.table

    def __str__(self, root=None, rroot=None):
        r = ''

        for join in self:

            if root is None:
                graph = self.entities.orm.table
            else:
                graph = root

            if rroot is None:
                rgraph = self.table
            else:
                rgraph = '%s.%s' % (rroot, self.table)

            if join.type == join.Inner:
                r += 'INNER JOIN'
            elif join.type == join.Leftouter:
                r += 'LEFT OUTER JOIN'
            else:
                raise ValueError('Invalid join type')

            jointbl = join.entities.orm.table
            graph = '%s.%s' % (graph, jointbl)
            tbl = ' %s' % jointbl
            r += '%s AS `%s`' % (tbl, graph)

            mypk = self.entities.orm.mappings.primarykeymapping.name
            for map in join.entities.orm.mappings.foreignkeymappings:
                if self.entities.orm.entity is map.entity:
                    joinpk = map.name
                    break
            else:
                msg = 'FK not found: '
                msg += '%s.%s = %s.%s'
                msg %= (jointbl, '<NOT FOUND>', rgraph, mypk)
                msg += "\nIs '%s' a parent to '%s'" % (rgraph, jointbl)
                raise ValueError(msg)

            r += '\n    ON `%s`.%s = %s.%s'
            r %= (graph, joinpk, '`%s`' % rgraph, mypk)

            # TODO This assignment seems unnecessary
            js = join.entities.orm.joins

            r += '\n' + join.entities.orm.joins.__str__(root=graph, rroot=rgraph)

        return r

    @property
    def wheres(self):
        return wheres(initial=[x.where for x in self if x.where])

    # TODO REMOVEME
    def getwheres(self, graph=None):
        whs = wheres()

        if graph is None:
            graph = self.table
        else:
            graph = '%s.%s' % (graph, self.table)

        for j in self:
            if not j.where:
                continue

            wh = j.where.clone()
            wh.alias = '%s.%s' % (graph, wh.alias)
            whs += wh

        return whs

class join(entitiesmod.entity):
    Inner = 0
    Leftouter = 0

    def __init__(self, es, type):
        self.entities = es
        self.type = type # inner, outer, etc

    @property
    def table(self):
        return self.entities.orm.table

    @property
    def where(self):
        return self.entities.orm.where

    def __repr__(self):
        name = type(self.entities).__name__
        typ = 'INNER' if self.type == self.Inner else 'LEFT OUTER'
        return 'join(%s, %s)' % (name, typ)

class wheres(entitiesmod.entities):
    pass

class where(entitiesmod.entity):
    def __init__(self, es, pred, args):
        self.entities     =  es
        self.predicate    =  None
        self._args        =  None
        self._alias       =  None

        # TODO Answer why a where clause would not have a pred or an args
        if pred:
            pred = orm.introduce(pred, args)
            self.predicate = predicate(pred)

        if args:
            self.args = args

        
    def clone(self):
        return where(
            self.entities,
            self.predicate, # TODO Do we need to clone the predicate?
            self.args
        )

    def __str__(self, graph=''):
        ''' Return a string representation of the WHERE clause with %s
        parameters. If the where object's entities collection has joins, those
        joins will be traversed to captures all where clauses. '''

        # Start off with a 'WHERE '
        r = '' if graph else 'WHERE '

        # Maintain a cumilitive graph string which denotes the hierarchy as we
        # recurse back into this method
        tbl = self.entities.orm.table
        graph = ('%s.%s') % (graph, tbl) if graph else tbl

        # Concatentate the predicate with graph to return string
        r += '(%s)' % self.predicate.__str__(columnprefix=graph)

        # Recursively join `where` predicates into the return variable.
        # Recursions can happen via this join() function, or, if a `where'
        # object is available on the `join` object, a call to the `where`'s
        # __str__ method will result in recursion instead.
        def join(js):
            nonlocal graph
            nonlocal r
            for j in js:
                if j.where:
                    # If a join object has a where, use it's where to stringify the
                    # predicate.

                    # Recurse into the join's where's __str__ passing in graph
                    r += '\n AND %s' % j.where.__str__(graph=graph)
                else:
                    # If the join object has no where object, use the join's
                    # entities' joins collections and recursively call this
                    # join method.
                    js = j.entities.orm.joins
                    tbl = j.entities.orm.table
                    oldgraph, graph = graph, ('%s.%s') % (graph, tbl)
                    join(js)
                    graph = oldgraph

        # Call join with this where objects entities' joins
        join(self.entities.orm.joins)

        return r

    def __repr__(self):
        return '%s\n%s' % (self.predicate, self.args)
    
class predicates(entitiesmod.entities):
    pass

class predicate(entitiesmod.entity):
    Specialops = '=', '==', '<', '<=', '>', '>=', '<>'
    Wordops = 'LIKE', 'NOT', 'NOT LIKE', 'IS', 'IS IN', 'IS NOT', 'IS NOT IN', 'BETWEEN', 'NOT BETWEEN'
    Constants = 'TRUE', 'FALSE', 'NULL'
    Ops = Specialops + Wordops
    
    def __init__(self, expr, junctionop=None):
        self._operator    =  ''
        self.operands     =  list()
        self.match        =  None
        self._junction    =  None
        self._junctionop  =  junctionop
        self.startparen   =  0
        self.endparen     =  0

        if isinstance(expr, shlex):
            lex = expr
        else:
            # TODO When we get to Python 3.6, we can use the punctuation_chars
            # argument to shlex.__init__ which will make operator parsing
            # easier.
            lex = shlex(expr, posix=False, punctuation_chars='!=<=>')

        self._parse(lex)

    def __iter__(self):
        yield self
        if self.match and self.match.junction:
            for pred in self.match.junction:
                yield  pred 

        if self.junction:
            for pred in self.junction:
                yield pred

        raise StopIteration

    @property
    def junction(self):
        return self._junction

    @junction.setter
    def junction(self, v):
        self._junction = v

    @property
    def junctionop(self):
        if self._junctionop:
            return self._junctionop.strip().upper()
        return None

    @property
    def columns(self):
        return [op for op in self.operands if self._iscolumn(op)]

    @staticmethod
    def _raiseSyntaxError(lex, tok, ex=None, msg=''):
        if not ex:
            ex = predicate.SyntaxError

        cur = lex.instream.tell()
        str = lex.instream.getvalue()
        strlen = len(str)
        start = max(0, cur - 10)
        stop = min(strlen, cur + 10)
        snippet = str[start: stop]

        raise ex(cur, snippet, tok, msg=msg)
    
    def _demandBalancedParens(self):
        if self.junctionop:
            return

        startparen = endparen = 0
        for pred in self:
            startparen += pred.startparen
            endparen += pred.endparen


        if endparen != startparen:
            raise predicate.ParentheticalImbalance(startparen, endparen)

    def _parse(self, lex):
        tok = lex.get_token()
        inbetween      =  False
        inquote        =  False
        inplaceholder  =  False
        unexpected = predicate.UnexpectedToken

        while tok != lex.eof:
            TOK = tok.upper()

            if tok == '%':
                inplaceholder = True
            elif inplaceholder:
                if tok == 's':
                    self.operands.append('%s')
                else:
                    msg = 'Unexpected placeholder type. ' + \
                          'Consider using %s instead'
                    self._raiseSyntaxError(lex, tok, ex=unexpected, msg=msg)
                inplaceholder = False
                
            elif self._iscolumn(tok):
                self.operands.append(tok)

            elif TOK == 'MATCH':
                self.operands = None
                self.operator = None
                self.match = predicate.Match(lex)

            elif self._iswordoperator(tok):
                self.operator += ' ' + tok
                if TOK == 'BETWEEN':
                    inbetween = True

            elif self._lookslikeoperator(lex, tok):
                if self.operator:
                    self._raiseSyntaxError(lex, tok, ex=unexpected)
                    
                if not len(self.operands):
                    self._raiseSyntaxError(lex, tok, ex=unexpected)

                if not self._isoperator(tok):
                    raise predicate.InvalidOperator(tok)

                self.operator = tok

            elif self._isliteral(tok):
                tok = TOK if TOK in self.Constants else tok
                if inquote:
                    if tok[0] == "'":
                        self.operands[-1] += tok
                else:
                    inquote = True # Maybe
                    self.operands.append(tok)

            elif TOK in ('AND', 'OR'):
                if not self.match and not len(self.operands):
                    self._raiseSyntaxError(lex, tok, ex=unexpected)

                if not (inbetween and TOK == 'AND'):
                    self.junction = predicate(lex, tok)
                    self._demandBalancedParens()
                    return

            elif tok == '(':
                self.startparen += 1

            elif tok == ')':
                self.endparen += 1

            if inbetween and len(self.operands) == 3:
                inbetween = False

            tok = lex.get_token()

            if tok != lex.eof and tok[-1] != "'":
                inquote = False

        if not self.match:
            if self.operator in ('BETWEEN', 'NOT BETWEEN'):
                if len(self.operands) != 3:
                    msg = 'Expected 2 operands, not %s' % len(self.operands)
                    self._raiseSyntaxError(lex, tok, ex=unexpected, msg=msg)
            else:
                if len(self.operands) != 2:
                    msg = 'Expected 2 operands, not %s' % len(self.operands)

                    self._raiseSyntaxError(lex, tok, ex=unexpected, msg=msg)

            # TODO When the punctuation_chars argument is available in shlex, we can
            # capture bad operators when they happen and report the column number.
            if self.operator not in predicate.Ops:
                raise predicate.InvalidOperator(self.operator)

        self._demandBalancedParens()
                

    @property
    def operator(self):
        if self._operator is None:
            return None
        return self._operator.strip().upper()

    @operator.setter
    def operator(self, v):
        self._operator = v

    def __str__(self, columnprefix=None):
        # TODO Uppercase TRUE, FALSE and NULL literals

        r = str()

        r += ' %s ' % self.junctionop if self.junctionop else ''

        r += '(' * self.startparen

        # TODO Pass columnprefix to match
        if self.match:
            r += str(self.match)
            if self.match.junction:
                r += str(self.match.junction)
        else:
            cnt = len(self.operands)
            # TODO Limit the size of these lines to 80 chars
            # TODO We shouldn't have 1 operand anymore. That was a mistake (not col)
            if cnt == 1:
                r += '%s %s' % (self.operator, self.operands[0])
            elif cnt == 2:
                ops = self.operands.copy()
                if columnprefix:
                    for i, op in enumerate(ops):
                        if self._iscolumn(op):
                            ops[i] = '`%s`.%s' % (columnprefix, op)
                r += '%s %s %s' % (ops[0], self.operator, ops[1])
            elif self.operator in ('BETWEEN', 'NOT BETWEEN'):
                r += '%s %s %s AND %s' % (self.operands[0], self.operator, *self.operands[1:])
            else:
                raise ValueError('Incorrect number of operands')

        r += ')' * self.endparen

        junc = self.junction
        if junc:
            r += junc.__str__(columnprefix=columnprefix)

        return r

    def __repr__(self):
        return "predicate('%s')" % str(self)

    @staticmethod
    def _iscolumn(tok):
        # TODO true, false and null are literals, not columns
        # TODO Support underscores in column names
        TOK = tok.upper()
        return     not predicate._isoperator(tok) \
               and not predicate._isliteral(tok) \
               and tok[0].isalpha()           \
               and tok.isalnum()              \
               and TOK not in ('AND', 'OR', 'MATCH')

    @staticmethod
    def _lookslikeoperator(lex, tok):
        for c in tok:
            if c not in lex.punctuation_chars:
                return False
        return True

    @staticmethod
    def _isoperator(tok):
        return tok.upper() in predicate.Ops + predicate.Wordops

    @staticmethod
    def _iswordoperator(tok):
        return tok.upper() in predicate.Wordops

    @staticmethod
    def _isliteral(tok):
        # TODO true, false and null are literals, not columns
        fl = ''.join((tok[0], tok[-1]))

        # If quoted
        if fl in ('""', "''"):
            return True

        # If numeric
        if tok.isnumeric():
            return True

        return tok.upper() in predicate.Constants

    class Match():
        # TODO Fix below line by using flags=re.IGNORECASE
        re_alphanum_ = re.compile('^[A-Za-z_][A-Za-z_0-9]+$')

        re_isnatural = re.compile(
            r'^\s*in\s+natural\s+language\s+mode\s*$', \
              flags=re.IGNORECASE
        )

        re_isboolean = re.compile(
            r'^\s*in\s+boolean\s+mode\s*$',\
             flags=re.IGNORECASE
        )

        def __init__(self, lex):
            self._lex            =  lex
            self.columns         =  list()
            self.searchstring    =  str()
            self._mode           =  str()
            self.junction        =  None
            self._parse(lex)

        def _parse(self, lex):
            tok = lex.get_token()
            incolumns  =  False
            insearch   =  False
            inagainst  =  False
            inmode     =  False

            while tok != lex.eof:
                TOK = tok.upper()
                if incolumns:
                    if self._iscolumn(tok):
                        self.columns.append(tok)

                elif insearch:
                    # TODO Test search strings with quotes
                    if tok == ')':
                        ex=predicate.UnexpectedToken
                        msg = 'Missing search string'
                        predicate._raiseSyntaxError(lex, tok, ex=ex, msg=msg)

                    self.searchstring = tok.strip("'")
                    insearch = False

                elif inmode:
                    if TOK in ('IN', 'NATURAL', 'BOOLEAN', 'LANGUAGE', 'MODE'):
                        self._mode += ' ' + TOK

                    elif TOK in ('AND', 'OR'):
                        self.junction = predicate(lex, tok)

                    elif tok == ')':
                        lex.push_token(tok)
                        return

                    else:
                        ex=predicate.UnexpectedToken
                        msg = 'Check spelling of search modifiers '
                        predicate._raiseSyntaxError(lex, tok, ex=ex, msg=msg)

                if tok == '(':
                    if len(self.columns) and not inagainst:
                        ex=predicate.UnexpectedToken
                        msg = 'Are you missing the AGAINST keyword'
                        predicate._raiseSyntaxError(lex, tok, ex=ex, msg=msg)

                    incolumns = not len(self.columns)
                    insearch = inagainst

                elif tok == ')':
                    if incolumns and not len(self.columns):
                        ex=predicate.UnexpectedToken
                        msg = 'Missing columns list'
                        predicate._raiseSyntaxError(lex, tok, ex=ex, msg=msg)

                    incolumns = False
                    if inagainst:
                        inmode = True
                    else:
                        inagainst = False

                elif TOK == 'AGAINST':
                    inagainst = True

                tok = lex.get_token()

            try:
                self.mode
            except:
                ex=predicate.UnexpectedToken
                msg = 'Invalid search modifiers'
                predicate._raiseSyntaxError(lex, tok, ex=ex, msg=msg)
                

        @property
        def mode(self):
            mode = self._mode.strip()

            if not mode:
                return 'natural'

            if self.re_isnatural.match(mode):
                return 'natural'

            if self.re_isboolean.match(mode):
                return 'boolean'

            raise ValueError('Incorrect mode: ' + mode)

        def __repr__(self):
            return "Match('%s')" % str(self)

        def __str__(self):
            args = ', '.join(self.columns), self.searchstring
            r = "MATCH (%s) AGAINST ('%s')" % args

            if self.mode == 'natural':
                r += ' IN NATURAL LANGUAGE MODE'
            elif self.mode == 'boolean':
                r += ' IN BOOLEAN MODE'
                
            return r

        def _iscolumn(self, buff):
            return self.re_alphanum_.match(buff)

    class SyntaxError(ValueError):
        def __init__(self, col=None, ctx=None, tok=None, msg=None):
            self.column = col
            self.context = ctx
            self.token = tok
            self.message = msg

        def __str__(self):
            args = (self.column, self.context)

            if self.column:
                msg = "Syntax error at column %s near '%s'" % args
            elif self.context:
                msg = "Syntax error %s near '%s'" % self.context
                
            if self.message:
                msg += '. ' + self.message

            return msg

    class ParentheticalImbalance(SyntaxError):
        def __init__(self, startparen, endparen):
            self.startparen = startparen
            self.endparen = endparen

        def __str__(self):
            msg = 'Parenthetical imbalance. '
            return msg

    class InvalidOperator(SyntaxError):
        def __init__(self, op):
            self.operator = op

        def __str__(self):
            return 'Invalid operator: ' + self.operator

    class UnexpectedToken(SyntaxError):
        def __str__(self):
            msg = ''
            if self.token:
                msg += 'Unexpected token: "%s"' % self.token

            msg = super().__str__() + '. ' + msg
            return msg


class allstream(stream):
    pass
        
class classproperty(property):
    ''' Add this decorator to a method and it becomes a class method
    that can be used like a property.'''

    def __get__(self, cls, owner):
        # If cls is not None, it will be the instance. If there is an instance,
        # we want to pass that in instead of the class (owner). This makes it
        # possible for classproperties to act like classproperties and regular
        # properties at the same time. See the conditional at entities.count.
        obj = cls if cls else owner
        return classmethod(self.fget).__get__(None, obj)()

class entities(entitiesmod.entities):

    @classproperty
    def all(cls):
        return cls(allstream)

    re_alphanum_ = re.compile('^[A-Za-z_][A-Za-z_]+$')

    def __init__(self, initial=None, _p2=None, *args, **kwargs):
        # TODO Ensure kwargs are in self.orm.mappings collections. Raise
        # ValueError if any are not there.
        try:
            self.orm = self.orm.clone()
        except AttributeError:
            msg = (
                "Can't instantiate abstract orm.entities. "
                "Use entities.entities for a generic entities collection "
                "class."
            )
            raise NotImplementedError(msg)

        self.orm.instance = self
        self.orm.isloaded = False
        self.orm.isloading = False
        self.orm.stream = None
        self.orm.where = None
        self.orm.ischunk = False
        self.orm.joins = joins(es=self)

        self.onbeforereconnect  =  entitiesmod.event()
        self.onafterreconnect   =  entitiesmod.event()
        self.onafterload        =  entitiesmod.event()

        self.onafterload       +=  self._self_onafterload

        # If a stream is found in the first or second argument, move it to
        # args
        args = list(args)
        if  isinstance(initial, stream):
            args.append(initial)
            initial = None
        elif type(initial) is type and stream in initial.mro():
            args.append(initial())
            initial = None
        elif _p2 is stream or isinstance(_p2, stream):
            args.append(_p2)
            _p2 = None

        # Look in *args for stream class or a stream object. If found, ensure
        # the element is an instantiated stream and set it to self._stream.
        # Delete the stream from *args.
        for i, e in enumerate(args):
            if e is stream:
                self.orm.stream = stream()
                self.orm.stream.entities = self
                del args[i]
                break
            elif isinstance(e, stream):
                self.orm.stream = e
                self.orm.stream.entities = self
                del args[i]
                break

        # The parameters express a conditional (predicate) if the first is
        # a str, or the arg and kwargs are not empty. Otherwise, the first
        # parameter, `initial`, means an initial set of values that the
        # collections should be set to.  The other parameters will be empty
        # in that case.
        iscond = type(initial) is str
        iscond = iscond or (initial is None and (_p2 or bool(args) or bool(kwargs)))

        if self.orm.stream or iscond:
            super().__init__()

            _p1 = '' if initial is None else initial
            self._preparepredicate(_p1, _p2, *args, **kwargs)
            return

        super().__init__(initial=initial)

    def clone(self, to=None):
        if not to:
            raise NotImplementedError()

        to.where         =  self.where
        to.orm.stream    =  self.orm.stream
        to.orm.isloaded  =  self.orm.isloaded

    def _self_onafterload(self, src, eargs):
        chron = db.chronicler.getinstance()
        chron += db.chronicle(eargs.entity, eargs.op, eargs.sql, eargs.args)

    def innerjoin(self, *args):
        for es in args:
            self.join(es, join.Inner)

    def join(self, es, type=None):
        type = joins.Inner if type is None else type
        self.orm.joins += join(es=es, type=type)
    
    @classproperty
    def count(cls):
        # If type(cls) is type then count is being called directly off the
        # class:
        #
        #   artists.count
        #
        # In this case, we get the all stream and use its count proprety
        # because the request is interpreted as "give me the the number of rows
        # in the artists table.
        #
        # If type(cls) is not type, it is being called of an instance.
        #   artists().count
        # 
        # cls is actuallly a reference to the instance (artists())
        # In this case, we just want the number of entities in the given
        # collection.
        if type(cls) is type:
            return cls.all.count
        else:
            # TODO Subscribe to executioner's on*connect events

            self = cls
            if self.orm.isstreaming:
                sql = 'SELECT COUNT(*) FROM ' + self.orm.table
                if self.orm.where.conditional:
                    # TODO Update for joins
                    sql += ' WHERE ' + self.orm.where.conditional

                ress = None
                def exec(cur):
                    nonlocal ress
                    cur.execute(sql, self.orm.where.args)
                    ress = db.dbresultset(cur)

                db.executioner(exec).execute()

                return ress.first[0]
            else:
                return super().count

    def __iter__(self):
        if self.orm.isstreaming:
            for es in self.orm.stream.cursor:
                for e in es:
                    yield e
        else:
            for e in super().__iter__():
                yield e

    def __getitem__(self, key):
        if self.orm.isstreaming:
            cur = self.orm.stream.cursor
            es = cur.advance(key)
            if isinstance(key, int):
                if es.hasone:
                    return es.first
                raise IndexError('Entities index out of range')
            return es
                
        else:
            e = super().__getitem__(key)
            if hasattr(e, '__iter__'):
                return type(self)(initial=e)
            else:
                return e
    
    def __getattribute__(self, attr):
        if attr == 'orm' or not self.orm.isstreaming:
            return object.__getattribute__(self, attr)

        nonos = (
            'getrandom',    'getrandomized',  'where',    'clear',
            'remove',       'shift',          'pop',      'reversed',
            'reverse',      'insert',         'push',     'has',
            'unshift',      'append',         '__sub__',  'getcount',
            '__setitem__',  'getindex',       'delete'
        )

        if attr in nonos:
            msg = "'%s's' attribute '%s' is not available "
            msg += 'while streaming'
            raise AttributeError(msg % (self.__class__.__name__, attr))

        return proceed()

    def sort(self, key=None, reverse=None):
        key = 'id' if key is None else key
        if self.orm.isstreaming:
            key = '%s %s' % (key, 'DESC' if reverse else 'ASC')

            self.orm.stream.orderby = key
        else:
            reverse = False if reverse is None else reverse
            super().sort(key, reverse)

    def sorted(self, key=None, reverse=None):
        key = 'id' if key is None else key
        if self.orm.isstreaming:
            key = '%s %s' % (key, 'DESC' if reverse else 'ASC')

            self.orm.stream.orderby = key
            return self
        else:
            reverse = False if reverse is None else reverse

            # TODO Why was self being reloaded?
            #self.load()
            r =  super().sorted(key, reverse)
            self.clone(r)
            return r

    def save(self, *es):
        exec = db.executioner(self._save)
        exec.execute(es)

    def _save(self, cur, es=None):
        for e in self:
            e._save(cur)

        for e in self.orm.trash:
            e._save(cur)

        if es:
            for e in es:
                e._save(cur)

    def delete(self):
        for e in self:
            e.delete()
        
    def give(self, es):
        sts = self.orm.persistencestates
        super().give(es)

        # super().give(es) will mark the entities for deletion
        # (ismarkedfordeletion) since it removes entities from collections.
        # However, giving an entity to another collection is a matter of
        # updating its foreign key/composite. So restore the original
        # persistencestates of the entities then make sure they are all still
        # dirty (isdirty). This will keep them from being deleted unless that
        # had previously been explitly marked for deletion.

        es.orm.persistencestates = sts
        for e in es:
            e.orm.isdirty = True

    def append(self, obj, uniq=False, r=None):
        if isinstance(obj, entities):
            for e in obj:
                self.append(e, r=r)
            return

        for clscomp in self.orm.composites:
            try:
                objcomp = getattr(self, clscomp.__name__)

            except Exception as ex:
                # The self collection won't always have a reference to its
                # composite.  For example: when the collection is being
                # lazy-loaded.  The lazy-loading, however, will ensure the obj
                # being appended will get this reference.
                continue
            else:
                # Assign the composite reference of this collection to the obj
                # being appended, i.e.:
                #    obj.composite = self.composite
                setattr(obj, clscomp.__name__, objcomp)

        super().append(obj, uniq, r)
        return r

    def _preparepredicate(self, _p1='', _p2=None, *args, **kwargs):
        p1, p2 = _p1, _p2

        if p2 is None and p1 != '':
            msg = '''
                Missing arguments collection.  Be sure to add arguments in the
                *args portion of the constructor.  If no args are needed for
                the query, just pass an empty tuple to indicate you none are
                needed.  Note that this is an opportunity to evaluate whether
                or not you are opening up an SQL injection attact vector.
            '''
            raise ValueError(textwrap.dedent(msg).lstrip())

        args = list(args)
        for k, v in kwargs.items():
            if p1: 
                p1 += ' and '
            p1 += '%s = %%s' % k
            args.append(v)

        p2isscaler = p2isiter = False

        if p2 is not None:
            if type(p2) is not str and hasattr(p2, '__iter__'):
                p2isiter = True
            else:
                p2isscaler = True

        if p2 is not None:
            if p2isscaler:
                # TODO re_alphanum_ should allow for numbers after first
                # character, but doesn't.
                if self.re_alphanum_.match(p1):
                    # If p1 looks like a simple column name (alphanums,
                    # underscores, no operators) assume the user is doing a
                    # simple equailty test (p1 == p2)
                    p1 += ' = %s'
                args = [p2] + args
            else: # tuple, list, etc
                args = list(p2) + args

        args = [x.bytes if type(x) is UUID else x for x in args]

        self.orm.where = where(self, p1, args)

    def clear(self):
        self.orm.isloaded = False
        try:
            # Set isremoving to True so entities.__getattribute__ doesn't
            # attempt to load whenever the removing logic calls an attibute on
            # the entities collection.
            self.orm.isremoving = True
            super().clear()
        finally:
            self.orm.isremoving = False


    def remove(self, *args, **kwargs):
        try:
            # Set isremoving to True so entities.__getattribute__ doesn't
            # attempt to load whenever the removing logic calls an attibute on
            # the entities collection.
            self.orm.isremoving = True
            super().remove(*args, **kwargs)
        finally:
            self.orm.isremoving = False


    def load(self, orderby=None, limit=None, offset=None):
        if self.orm.isloaded:
            return

        try:
            self.orm.isloading = True

            sql, args = self.orm.sql

            if orderby:
                sql += ' ORDER BY ' + orderby

            if limit is not None:
                offset = 0 if offset is None else offset
                sql += ' LIMIT %s OFFSET %s' % (limit, offset)

            ress = None
            def exec(cur):
                nonlocal ress
                cur.execute(sql, args)
                ress = db.dbresultset(cur)

            exec = db.executioner(exec)

            exec.onbeforereconnect += \
                lambda src, eargs: self.onbeforereconnect(src, eargs)
            exec.onafterreconnect  += \
                lambda src, eargs: self.onafterreconnect(src, eargs)

            exec.execute()

            eargs = db.operationeventargs(self, 'retrieve', sql, args)
            self.onafterload(self, eargs)

            for res in ress:
                # TODO Tighten up using where()
                id = UUID(bytes=res.fields.first.value)
                for e in self:
                    if e.id == id:
                        # TODO Test for multi-row
                        break
                else:
                    e = self.orm.entity()
                    self += e

                e.orm.populate(res)

                e.orm.persistencestate = (False,) * 3
        finally:
            self.orm.isloaded = True
            self.orm.isloading = False

    def _getbrokenrules(self, es=None, followentitymapping=True):
        brs = entitiesmod.brokenrules()
        for e in self:
            #if self.orm.entities not in e.orm.entities.mro():
            if not isinstance(e, self.orm.entity):
                prop = type(self).__name__
                msg = "'%s' collection contains a '%s' object"
                msg %= (prop, type(e).__name__)
                brs += entitiesmod.brokenrule(msg, prop, 'valid')
                
            brs += e._getbrokenrules(es, followentitymapping=followentitymapping)
        return brs

    def _self_onremove(self, src, eargs):
        self.orm.trash += eargs.entity
        self.orm.trash.last.orm.ismarkedfordeletion = True
        super()._self_onremove(src, eargs)
                    
    def getindex(self, e):
        if isinstance(e, entity):
            for ix, e1 in enumerate(self):
                if e.id == e1.id: return ix
            e, id = e.orm.entity.__name__, e.id
            raise ValueError("%s[%s] is not in the collection" % (e, id))

        super().getindex(e)

    def __repr__(self):
        hdr = '%s object at %s count: %s\n' % (type(self), 
                                               hex(id(self)), 
                                               self.count)

        tbl = table()
        r = tbl.newrow()
        r.newfield('Address')
        r.newfield('id')
        r.newfield('str')
        r.newfield('Broken Rules')

        for e in self:
            r = tbl.newrow()
            r.newfield(hex(id(e)))
            r.newfield(e.id.hex[:8])
            r.newfield(str(e))
            b = ''
            for br in e.brokenrules:
                b += '%s:%s ' % (br.property, br.type)
            r.newfield(b)

        return '%s\n%s' % (hdr, tbl)

class entitymeta(type):
    def __new__(cls, name, bases, body):
        # If name == 'entity', the `class entity` statement is being executed.
        if name not in ('entity', 'association'):
            ormmod = sys.modules['orm']
            orm_ = orm()
            orm_.mappings = mappings(orm=orm_)

            try:
                body['entities']
            except KeyError:
                for sub in orm_.getsubclasses(of=entities):

                    if sub.__name__   == name + 's' and \
                       sub.__module__ == body['__module__']:

                        body['entities'] = sub
                        break
                else:
                    msg =  "Entities class coudn't be found. "
                    msg += "Either specify one or define one with a predictable name"
                    raise AttributeError(msg)

            orm_.entities = body['entities']
            orm_.entities.orm = orm_

            del body['entities']

            try:
                orm_.table = body['table']
                del body['table']
            except KeyError:
                orm_.table = orm_.entities.__name__

            body['id'] = primarykeyfieldmapping()
            body['createdat'] = fieldmapping(datetime)
            body['updatedat'] = fieldmapping(datetime)

            for k, v in body.items():

                if k.startswith('__'):
                    continue
                
                if isinstance(v, mapping):
                    map = v
                elif v in fieldmapping.types:
                    map = fieldmapping(v)
                elif type(v) is tuple:
                    args, kwargs = [], {}
                    for e in v:
                        isix = (
                            hasattr(e, 'mro') and index in e.mro()
                            or isinstance(e, index)
                        )
                        if isix:
                            kwargs['ix'] = e
                        else:
                            args.append(e)

                    map = fieldmapping(*args, **kwargs)

                elif hasattr(v, 'mro'):
                    mro = v.mro()
                    if ormmod.entities in mro:
                        map = entitiesmapping(k, v)
                    elif ormmod.entity in mro:
                        map = entitymapping(k, v)
                    else:
                        raise ValueError()
                else:
                    if type(v) is ormmod.attr.wrap:
                        map = v.mapping
                    else:
                        continue
               
                map._name = k
                orm_.mappings += map

            for map in orm_.mappings:
                try:
                    prop = body[map.name]
                    if type(prop) is ormmod.attr.wrap:
                        body[map.name] = prop
                    else:
                        del body[map.name]
                except KeyError:
                    # The orm_.mappings.__iter__ adds new mappings which won't
                    # be in body, so ignore KeyErrors
                    pass

            body['orm'] = orm_

        entity = super().__new__(cls, name, bases, body)

        if name not in ('entity', 'association'):
            orm_.entity = entity

            # Since a new entity has been created, invalidate the derived cache
            # of each mappings collection's object.  They must be recomputed
            # since they are based on the existing entity object available.
            for e in orm.getentitys():
                e.orm.mappings._populated = False

        return entity

class entity(entitiesmod.entity, metaclass=entitymeta):
    def __init__(self, o=None, _depth=0):
        self.orm = self.orm.clone()
        self.orm.instance = self

        self.onbeforesave       =  entitiesmod.event()
        self.onaftersave        =  entitiesmod.event()
        self.onafterload        =  entitiesmod.event()
        self.onbeforereconnect  =  entitiesmod.event()
        self.onafterreconnect   =  entitiesmod.event()

        self.onaftersave       +=  self._self_onaftersave
        self.onafterload       +=  self._self_onafterload
        self.onafterreconnect  +=  self._self_onafterreconnect

        if o is None:
            self.orm.isnew = True
            self.orm.isdirty = False
            self.id = uuid4()
        else:
            if type(o) is UUID:
                res = self._load(o)
            else:
                res = o

            self.orm.populate(res)

        super().__init__()

        # Post super().__init__() events
        self.onaftervaluechange  +=  self._self_onaftervaluechange

    def __getitem__(self, args):
        if type(args) is str:
            try:
                return getattr(lself, args)
            except AttributeError as ex:
                raise IndexError(str(ex))

        vals = []

        for arg in args:
            vals.append(self[arg])

        return tuple(vals)

    def __call__(self, args):
        try:
            return self[args]
        except IndexError:
            return None

    def __setitem__(self, k, v):
        map = self.orm.mappings(k)
        if map is None:
           super = self.orm.super
           if super:
               map = super.orm.mappings[k]
           else:
               raise IndexError("Map index doesn't exist: %s" % (k,))
        
        map.value = v

    # Move to orm
    def _load(self, id):
        sql = 'SELECT * FROM {} WHERE id = _binary %s'
        sql = sql.format(self.orm.table)

        args = id.bytes,

        ress = None
        def exec(cur):
            nonlocal ress
            cur.execute(sql, args)
            ress = db.dbresultset(cur)

        exec = db.executioner(exec)

        exec.onbeforereconnect += \
            lambda src, eargs: self.onbeforereconnect(src, eargs)
        exec.onafterreconnect  += \
            lambda src, eargs: self.onafterreconnect(src, eargs)

        exec.execute()

        ress.demandhasone()
        res = ress.first

        eargs = db.operationeventargs(self, 'retrieve', sql, args)
        self.onafterload(self, eargs)

        return res
    
    def _self_onafterload(self, src, eargs):
        self._add2chronicler(eargs)

    def _self_onaftersave(self, src, eargs):
        self._add2chronicler(eargs)

    def _self_onafterreconnect(self, src, eargs):
        self._add2chronicler(eargs)

    @staticmethod
    def _add2chronicler(eargs):
        chron = db.chronicler.getinstance()
        chron += db.chronicle(eargs.entity, eargs.op, eargs.sql, eargs.args)

    def _self_onaftervaluechange(self, src, eargs):
        if not self.orm.isnew:
            self.orm.isdirty = True

    def __dir__(self):
        ls = super().__dir__() + self.orm.properties

        # Remove duplicates. If an entity has an explicit attribute, the name
        # of the attribute will come in from the call to super().__dir__()
        # while the name of its associated map will come in through
        # self.orm.properties
        return list(set(ls))

    def __setattr__(self, attr, v, cmp=True):
        # Need to handle 'orm' first, otherwise the code below that
        # calls self.orm won't work.
        
        if attr == 'orm':
            return object.__setattr__(self, attr, v)

        map = self.orm.mappings(attr)

        if map is None:
            super = self.orm.super
            if super and super.orm.mappings(attr):
                super.__setattr__(attr, v, cmp)
            else:
                return object.__setattr__(self, attr, v)
        else:
            # Call entity._setvalue to take advantage of its event raising
            # code. Pass in a custom setattr function for it to call. Use
            # underscores for the paramenters since we already have the values
            # it would pass in in this method's scope - execpt for the v
            # which, may have been processed (i.e, if it is a str, it will
            # have been strip()ed. 
            def setattr0(_, __, v):
                map.value = v

            self._setvalue(attr, v, attr, setattr0, cmp=cmp)

            if type(map) is entitymapping:
                e = v.orm.entity
                while True:
                    for map in self.orm.mappings.foreignkeymappings:
                        if map.entity is e:
                            self._setvalue(map.name, v.id, map.name, setattr0, cmp=cmp)
                            break;
                    else:
                        e = e.orm.super
                        if e:
                            continue
                        else:
                            # If we have gotten here, no FK was found in self
                            # that match the composite object passed in. This
                            # is probably because the wrong type of composite
                            # was given. The user/programmers has made a
                            # mistake. However, the brokenrules logic will
                            # detect this issue and alert the user to the
                            # issue.
                            pass
                    break

                # If self is a subentity (i.e., concert), we will want to set
                # the superentity's (i.e, presentation) composite map to it's
                # composite class (i.e., artist) value. 
                selfsuper = self.orm.super
                attrsuper = self.orm.mappings(attr).value.orm.super

                if selfsuper and attrsuper:
                    maps = selfsuper.orm.mappings
                    attr = maps(attrsuper.__class__.__name__).name
                    setattr(selfsuper, attr, attrsuper)

    @classmethod
    def reCREATE(cls, cur=None, recursive=False, clss=None):

        # Prevent infinite recursion
        if clss is None:
            clss = []
        else:
            if cls in clss:
                return
        clss += [cls]

        try: 
            if cur:
                conn = None
            else:
                # TODO Use executioner
                pool = db.pool.getdefault()
                conn = pool.pull()
                cur = conn.createcursor()

            try:
                cls.DROP(cur)
            except MySQLdb.OperationalError as ex:
                try:
                    errno = ex.args[0]
                except:
                    raise

                if errno != BAD_TABLE_ERROR: # 1051
                    raise

            cls.CREATE(cur)

            if recursive:
                for map in cls.orm.mappings.entitiesmappings:
                    map.entities.orm.entity.reCREATE(cur, True, clss)

                for ass in cls.orm.associations:
                    ass.entity.reCREATE(cur, True, clss)

                for sub in cls.orm.subclasses:
                    sub.reCREATE(cur)
                            
        except Exception as ex:
            # Rollback unless conn and cur weren't successfully instantiated.
            if conn and cur:
                conn.rollback()
            raise
        else:
            if conn:
                conn.commit()
        finally:
            if conn:
                pool.push(conn)
                if cur:
                    cur.close()

    @classmethod
    def DROP(cls, cur=None):
        # TODO Use executioner
        sql = 'drop table ' + cls.orm.table + ';'

        if cur:
            cur.execute(sql)
        else:
            pool = db.pool.getdefault()
            with pool.take() as conn:
                conn.query(sql)
    
    @classmethod
    def CREATE(cls, cur=None):
        # TODO Use executioner
        sql = cls.orm.mappings.createtable

        if cur:
            cur.execute(sql)
        else:
            pool = db.pool.getdefault()
            with pool.take() as conn:
                conn.query(sql)

    def delete(self):
        self.orm.ismarkedfordeletion = True
        self.save()

    def save(self, *es):
        # Create a callable to call self._save(cur) and the _save(cur)
        # methods on earch of the objects in *es.
        def save(cur):
            self._save(cur)
            for e in es:
                e._save(cur)

        # Create an executioner object with the above save() callable
        exec = db.executioner(save)

        # Register reconnect events of then executioner so they can be re-raised
        exec.onbeforereconnect += \
            lambda src, eargs: self.onbeforereconnect(src, eargs)
        exec.onafterreconnect  += \
            lambda src, eargs: self.onafterreconnect(src, eargs)

        # Call then executioner's exec methed which will call the exec() callable
        # above. executioner.execute will take care of dead, pooled connection,
        # and atomicity.
        exec.execute()
        
    def _save(self, cur=None, follow                  =True, 
                              followentitymapping     =True, 
                              followentitiesmapping   =True, 
                              followassociationmapping=True):

        if not self.orm.ismarkedfordeletion and not self.isvalid:
            raise db.brokenruleserror("Can't save invalid object" , self)

        if self.orm.ismarkedfordeletion:
            crud = 'delete'
            sql, args = self.orm.mappings.getdelete()
        elif self.orm.isnew:
            crud = 'create'
            self.createdat = self.updatedat = primative.datetime.utcnow()
            sql, args = self.orm.mappings.getinsert()
        elif self.orm._isdirty:
            self.updatedat = primative.datetime.utcnow()
            crud = 'update'
            sql, args = self.orm.mappings.getupdate()
        else:
            crud = None
            sql, args = (None,) * 2

        try:
            # Take snapshop of before state
            st = self.orm.persistencestate

            if sql:
                # Issue the query

                # Raise event
                eargs = db.operationeventargs(self, crud, sql, args)
                self.onbeforesave(self, eargs)

                cur.execute(sql, args)

                # Update new state
                self.orm.isnew = self.orm.ismarkedfordeletion
                self.orm.isdirty, self.orm.ismarkedfordeletion = (False,) * 2

                # Raise event
                self.onaftersave(self, eargs)
            else:
                # If there is no sql, then the entity isn't new, dirty or 
                # marked for deletion. In that case, don't save. However, 
                # allow any constituents to be saved.
                pass

            # For each of the constituent entities classes mapped to self,
            # set the foreignkeyfieldmapping to the id of self, i.e., give
            # the child objects the value of the parent id for their
            # foreign keys
            for map in self.orm.mappings if follow else tuple():

                if followentitymapping and type(map) is entitymapping:
                    # Call the entity constituent's save method. Setting
                    # followentitiesmapping to false here prevents it's
                    # child/entitiesmapping constituents from being saved. This
                    # prevents infinite recursion. 
                    if map.isloaded:
                        map.value._save(cur, followentitiesmapping=False,
                                             followassociationmapping=False)

                if followentitiesmapping and type(map) is entitiesmapping:

                    es = map.value

                    # es is None if the constituent hasn't been loaded,
                    # so conditionally save()
                    if es:
                        # Take snapshot of states
                        sts = es.orm.persistencestates

                        # Iterate over each entity and save them individually
                        for e in es:
                            
                            # Set the entity's FK to self.id value
                            for map in e.orm.mappings:
                                if type(map) is foreignkeyfieldmapping:
                                    if map.entity is self.orm.entity:
                                        # Set map.value to self.id. But rather
                                        # than a direct assignment, map.value =
                                        # self.id use setattr() to invoke the
                                        # _setvalue logic. This ensures that
                                        # the proper events get raised, but
                                        # even more importantly, it dirties e
                                        # so e's FK will be changed in the
                                        # database.  This is mainly for
                                        # instances where the constituent is
                                        # being moved to a different composite.
                                        setattr(e, map.name, self.id)
                                        break

                            # Call save(). If there is an Exception, restore state then
                            # re-raise
                            try:
                                # If self was deleted, delete each child
                                # constituents. Here, cascade deletes are
                                # hard-code.
                                if crud == 'delete':
                                    e.orm.ismarkedfordeletion = True
                                # If the previous operation on self was a
                                # delete, don't ascend back to self
                                # (followentitymapping == False). Doing so will
                                # recreate self in the database.
                                e._save(cur, followentitymapping=(crud!='delete'))
                            except Exception:
                                # Restore states
                                es.orm.persistencestates = sts
                                raise
                
                        for e in es.orm.trash:
                            trashst = e.orm.persistencestate
                            try:
                                e._save(cur)
                            except Exception:
                                e.orm.persistencestate = trashst
                                raise

                        # TODO If there is a rollback, shouldn't the entities
                        # be restored to the trash collection. Also, shouldn't
                        # deleting the associations trash (see below) do the
                        # same restoration.
                        es.orm.trash.clear()
                            
                if followassociationmapping and type(map) is associationsmapping:
                    if map.isloaded:
                        # For each association then each trashed association
                        for asses in map.value, map.value.orm.trash:
                            for ass in asses:
                                ass._save(cur, follow=False)
                                for map in ass.orm.mappings.entitymappings:
                                    if map.isloaded:
                                        if map.value is self:
                                            continue
                                        e = map.value
                                        e._save(cur, followassociationmapping=False)

                        asses.orm.trash.clear()

                if type(map) is foreignkeyfieldmapping:
                    if map.value is undef:
                        map.value = None

            super = self.orm.super
            if super:
                if crud == 'delete':
                    super.orm.ismarkedfordeletion = True
                super._save(cur)

        except Exception:
            self.orm.persistencestate = st
            raise
        
    # These are the limits of the MySQL datetime type
    mindatetime=primative.datetime('1000-01-01 00:00:00.000000+00:00')
    maxdatetime=primative.datetime('9999-12-31 23:59:59.999999+00:00')

    @property
    def brokenrules(self):
        return self._getbrokenrules()

    def _getbrokenrules(self, guestbook=None, followentitymapping=True):
        # TODO If an association is added that is the incorrect type, 
        # append a broken rule, i.e.:
        #
        #   arts.artifacts += location() 
        #   arts.artist_artifacts += location()
        #

        brs = entitiesmod.brokenrules()

        # This "guestbook" logic prevents infinite recursion and duplicated
        # brokenrules.
        guestbook = [] if guestbook is None else guestbook
        if self in guestbook:
            return brs
        else:
            guestbook += self,

        super = self.orm.super
        if super:
            brs += super._getbrokenrules(
                guestbook, 
                followentitymapping=followentitymapping
            )

        for map in self.orm.mappings:
            if type(map) is fieldmapping:
                t = map.type
                if t == types.str:
                    brs.demand(
                        self, 
                        map.name, 
                        type=str, 
                        min=map.min, 
                        max=map.max
                   )

                elif t == types.int:
                    brs.demand(self, map.name, min=map.min, max=map.max, 
                                     type=int)
                elif t == types.bool:
                    brs.demand(self, map.name, type=bool)

                elif t == types.float:
                    brs.demand(self, map.name, 
                                     type=float, 
                                     min=map.min, 
                                     max=map.max, 
                                     precision=map.precision,
                                     scale=map.scale)

                elif t == types.decimal:
                    brs.demand(self, map.name, 
                                     type=decimal.Decimal, 
                                     min=map.max, 
                                     max=map.min, 
                                     precision=map.precision,
                                     scale=map.scale)

                elif t == types.bytes:
                    brs.demand(self, 
                        map.name, 
                        type=bytes,
                        max=map.max, 
                        min=map.min
                    )

                elif t == types.datetime:
                    brs.demand(self, 
                        map.name, 
                        instanceof=datetime,
                        min=type(self).mindatetime,
                        max=type(self).maxdatetime,
                    )

            elif type(map) is entitiesmapping:
                # Currently, map.value will not load the entities on invocation
                # so we get None for es. This is good because we don't want to
                # needlessly load an object to see if it has broken rules.
                # However, if this changes, we will want to make sure that we
                # don't needlessy load this. This could lead to infinite
                # h (see it_entity_constituents_break_entity)
                es = map.value
                if es:
                    if not isinstance(es, map.entities):
                        msg = "'%s' attribute is wrong type: %s"
                        msg %= (map.name, type(es))
                        brs += entitiesmod.brokenrule(msg, map.name, 'valid')
                    brs += es._getbrokenrules(guestbook, 
                        followentitymapping=followentitymapping
                    )

            elif followentitymapping and type(map) is entitymapping:
                if map.isloaded:
                    v = map.value
                    if v:
                        if not isinstance(v, map.entity):
                            msg = "'%s' attribute is wrong type: %s"
                            msg %= (map.name, type(v))
                            args = msg, map.name, 'valid'
                            brs += entitiesmod.brokenrule(*args)
                        brs += v._getbrokenrules(guestbook, 
                            followentitymapping=followentitymapping
                        )
            elif type(map) is associationsmapping:
                if map.isloaded:
                    v = map.value
                    if v:
                        brs += v._getbrokenrules(guestbook)


        return brs

    def __getattribute__(self, attr):
        if attr in ('orm', '__class__'):
            return object.__getattribute__(self, attr)

        # self.orm.instance is set in entity.__init__. If the user overrides
        # __init__ and doesn't call the base __init__, self.orm.instance is
        # never set. Do a quick check here to inform the user if they forgot to
        # call the base __init__
        if self.orm.isstatic:
            msg = 'orm is static. '
            msg += 'Ensure the overridden __init__ called the base __init__'
            raise ValueError(msg)

        # TODO attr would never be 'orm', see above
        # TODO Why would self.orm.mappings ever be false... it's a collection
        if attr != 'orm' and self.orm.mappings:
            map = self.orm.mappings(attr)
            if not map:
                super = self.orm.super
                if super:
                    # TODO Before begining an ascent up the inheritence
                    # hierarchy, we need to first ensure that the attr is a map
                    # in that hierarchy; not just in the super. So the below
                    # line should be something like:
                    #     self.getmap(attr, recursive=True)
                    map = super.orm.mappings(attr)
                    if map:
                        if type(map) is entitymapping:
                            # We don't want an entitymapping from a super
                            # returned.  This would mean conc.artist would
                            # work. But concerts don't have artists;
                            # presentations do. Concerts have singers.
                            msg = "'%s' object has no attribute '%s'"
                            msg %= self.__class__.__name__, attr
                            raise AttributeError(msg)
                            
                        v = getattr(super, map.name)
                        # Assign the composite reference to the constituent
                        #   i.e., sng.presentations.singer = sng
                        if type(map) is entitiesmapping:
                            es = v
                            for e in (es,) +  tuple(es):
                                if not hasattr(e, self.orm.entity.__name__):
                                    setattr(e, self.orm.entity.__name__, self)
                        return v

        # Lazy-load constituent entities map
        if type(map) is entitiesmapping:
            if map.value is None:
                es = None
                if not self.orm.isnew:

                    # Get the FK map of the entities constituent. 
                    for map1 in map.entities.orm.mappings.foreignkeymappings:
                        e = self.orm.entity
                        while e:
                            if map1.entity is e:
                                break

                            # If not found, go up the inheritance tree and try again
                            super = e.orm.super
                            e = super.orm.entity if super else None
                        else:
                            continue
                        break
                    else:
                        raise ValueError('FK map not found for entity')

                    es = map.entities(map1.name, self.id)

                    def setattr1(e, attr, v):
                        e.orm.mappings(attr).value = v

                    # Assign the composite reference to the constituent's
                    # elements
                    #   i.e., art.presentations.first.artist = art
                    for e in es:
                        attr = self.orm.entity.__name__

                        # Set cmp to False and use a custom setattr. Simply
                        # calling setattr(e, attr, self) would cause e.attr to
                        # be loaded from the database for comparison when __setattr__
                        # calls _setvalue.  However, the composite doesn't need
                        # to be loaded from the database.
                        e._setvalue(attr, self, attr, cmp=False, setattr=setattr1)

                        # Since we just set e's composite, e now thinks its
                        # dirty.  Correct that here.
                        e.orm.persistencestate = (False,) * 3

                if es is None:
                    es = map.entities()

                map.value = es

                # Assign the composite reference to the constituent
                #   i.e., art.presentations.artist = art
                setattr(map.value, self.orm.entity.__name__, self)

                # Assign the superentities composite reference to the
                # constituent i.e., art.concert.artist = art
                super = self.orm.super
                if super:
                    setattr(map.value, super.orm.entity.__name__, super)

        elif type(map) is associationsmapping:
            map.composite = self

        elif type(map) is fieldmapping:
            if map.isexplicit:
                return object.__getattribute__(self, attr)

        elif map is None:
            if attr != 'orm':
                for map in self.orm.mappings.associationsmappings:
                    for map1 in map.associations.orm.mappings.entitymappings:
                        if map1.entity.orm.entities.__name__ == attr:
                            asses = getattr(self, map.name)
                            return getattr(asses, attr)

            return object.__getattribute__(self, attr)
            #msg = "'%s' object has no attribute '%s'"
            #raise AttributeError(msg % (self.__class__.__name__, attr))


        return map.value

    def __repr__(self):
        try:
            tbl = table()

            for map in self.orm.mappings:
                r = tbl.newrow()
                try:
                    v = getattr(self, map.name)
                except Exception as ex:
                    v = 'Exception: %s' % str(ex)
                    
                if type(map) in (primarykeyfieldmapping, foreignkeyfieldmapping):
                    if type(map.value) is UUID:
                        v = v.hex[:7]
                    else:
                        v = str(v)
                else:
                    try:
                        if type(map) in (entitiesmapping, associationsmapping):
                            es = v
                            if es:
                                brs = es._getbrokenrules(
                                    es=None, 
                                    followentitymapping=False
                                )
                                args = es.count, brs.count
                                v = 'Count: %s; Broken Rules: %s' % args
                            else:
                                v = str(es)
                        else:
                            v = str(v)
                    except Exception as ex:
                        v = '(%s)' % str(ex)

                r.newfield(map.name)
                r.newfield(v)

            tblbr = table()

            if not self.isvalid:
                r = tblbr.newrow()
                r.newfield('property')
                r.newfield('type')
                r.newfield('message')


                for br in self.brokenrules:
                    r = tblbr.newrow()
                    r.newfield(br.property)
                    r.newfield(br.type)
                    r.newfield(br.message)
                
            return '%s\n%s\n%s\n%s' % (super().__repr__(), 
                                       str(tbl), 
                                       'Broken Rules', 
                                       str(tblbr))
        except Exception as ex:
            return '%s (Exception: %s) ' % (super().__repr__(), str(ex))

    def __str__(self):
        if hasattr(self, 'name'):
            return '"%s"' % self.name
            
        return str(self.id)
            
class mappings(entitiesmod.entities):
    def __init__(self, initial=None, orm=None):
        super().__init__(initial)
        self._orm = orm
        self._populated = False
        self._populating = False
        self.oncountchange += self._self_oncountchange

    def _self_oncountchange(self, src, eargs):
        self._populated = False

    def __getitem__(self, key):
        self._populate()
        return super().__getitem__(key)

    def __iter__(self):
        self._populate()
        return super().__iter__()

    def _populate(self):
        if not self._populated and not self._populating:
            self._populating = True

            self.clear(derived=True)

            maps = []

            for map in self.entitymappings:
                maps.append(foreignkeyfieldmapping(map.entity, derived=True))

            for e in orm.getentitys():
                if e is self.orm.entity:
                    continue
                for map in e.orm.mappings.entitiesmappings:
                    if map.entities is self.orm.entities:
                        maps.append(entitymapping(e.__name__, e, derived=True))
                        maps.append(foreignkeyfieldmapping(e, derived=True))

            for ass in orm.getassociations():
                for map in ass.orm.mappings.entitymappings:
                    if map.entity is self.orm.entity:
                        asses = ass.orm.entities
                        map = associationsmapping(asses.__name__, asses, derived=True)
                        maps.append(map)
                        break

            for map in maps:
                self += map
            
            for map in self:
                map.orm = self.orm
                    
            self.sort()
            self._populating = False

        self._populated = True

    def clear(self, derived=False):
        if derived:
            for map in [x for x in self if x.derived]:
                self.remove(map)
        else:
            super().clear()

    def sort(self):
        # Make sure the mappings are sorted in the order they are
        # instantiated
        super().sort('_ordinal')

        # Ensure builtins attr's come right after id
        for attr in reversed(('id', 'createdat')):
            try:
                attr = self.pop(attr)
            except ValueError:
                # attr hasn't been added to self yet
                pass
            else:
                self << attr

        # Insert FK maps right after PK map
        fkmaps = list(self.foreignkeymappings)
        fkmaps.sort(key=lambda x: x.name)
        for map in fkmaps:
           self.remove(map)
           self.insertafter(0, map)

    @property
    def foreignkeymappings(self):
        return self._generate(type=foreignkeyfieldmapping)

    @property
    def primarykeymapping(self):
        return list(self._generate(type=primarykeyfieldmapping))[0]

    @property
    def entitiesmappings(self):
        return self._generate(type=entitiesmapping)

    @property
    def entitymappings(self):
        return self._generate(type=entitymapping)

    @property
    def associationsmappings(self):
        return self._generate(type=associationsmapping)

    def _generate(self, type):
        for map in self:
            if builtins.type(map) is type:
                yield map
    @property
    def orm(self):
        return self._orm

    @property
    def createtable(self):
        r = 'CREATE TABLE ' + self.orm.table + '(\n'

        for i, map in enumerate(self):
            if not isinstance(map, fieldmapping):
                continue

            if i:
                r += ',\n'

            r += '    ' + map.name

            if isinstance(map, fieldmapping):
                r += ' ' + map.dbtype

        for ix in self.aggregateindexes:
            r += ',\n    ' + str(ix)

        r += '\n) '
        r += 'ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;'
        return r

    @property
    def aggregateindexes(self):
        ixs = aggregateindexes()
        for map in self:
            if type(map) is fieldmapping and map.index:
                try:
                    ix = ixs[map.index.name]
                except IndexError:
                    ix = aggregateindex()
                    ixs += ix
                ix.indexes += map.index

        return ixs

    def getinsert(self):
        tbl = self.orm.table

        placeholder = ''
        for map in self:
            if isinstance(map, fieldmapping):
                placeholder += '%s, '

        placeholder = placeholder.rstrip(', ')

        sql = 'INSERT INTO {} VALUES ({});'.format(tbl, placeholder)

        args = self._getargs()

        sql = orm.introduce(sql, args)

        return sql, args

    def getupdate(self):
        set = ''
        for map in self:
            if isinstance(map, fieldmapping):
                if isinstance(map, primarykeyfieldmapping):
                    id = map.value.bytes
                else:
                    set += '%s = %%s, ' % (map.name,)

        set = set[:-2]

        sql = """UPDATE {}
SET {}
WHERE id = %s;
        """.format(self.orm.table, set)

        args = self._getargs()

        # Move the id value from the bottom to the top
        args.append(args.pop(0))

        sql = orm.introduce(sql, args)
        return sql, args

    def getdelete(self):
        sql = 'DELETE FROM {} WHERE id = %s;'.format(self.orm.table)

        args = self['id'].value.bytes,

        sql = orm.introduce(sql, args)

        return sql, args

    def _getargs(self):
        r = []
        for map in self:
            if isinstance(map, fieldmapping):
                keymaps = primarykeyfieldmapping, foreignkeyfieldmapping
                if type(map) in keymaps and isinstance(map.value, UUID):
                    r.append(map.value.bytes)
                else:
                    v = map.value if map.value is not undef else None
                    if v is not None:
                        if map.isdatetime:
                            v = v.replace(tzinfo=None)
                        elif map.isbool:
                            v = int(v)
                    r.append(v)
        return r

    def clone(self, orm_):
        r = mappings(orm=orm_)
        for map in self:
            r += map.clone()
        return r

class mapping(entitiesmod.entity):
    ordinal = 0

    def __init__(self, name, derived=False):
        self._name = name
        mapping.ordinal += 1
        self._ordinal = mapping.ordinal
        self.derived = derived

    @property
    def name(self):
        return self._name

    @property
    def fullname(self):
        return '%s.%s' % (self.orm.table, self.name)

    def __str__(self):
        return self.name

    @property
    def value(self):
        raise NotImplementedError('Value should be implemented by the subclass')

    @value.setter
    def value(self, v):
        raise NotImplementedError('Value should be implemented by the subclass')

    @property
    def isloaded(self):
        return self._value not in (None, undef)

    def clone(self):
        raise NotImplementedError('Abstract')
    
class associationsmapping(mapping):
    def __init__(self, name, ass, derived=False):
        self.associations = ass
        self._value = None
        self._composite = None
        super().__init__(name, derived)

    @property
    def composite(self):
        return self._composite

    @composite.setter
    def composite(self, v):
        self._composite = v
        
    @property
    def value(self):
        if not self._value:
            for map in self.associations.orm.mappings.foreignkeymappings:
                if map.entity is type(self.composite):
                    break
            else:
                raise ValueError('FK not found')

            asses = self.associations(map.name, self.composite.id)
            asses.composite = self.composite
            self.value = asses
        return self._value

    @value.setter
    def value(self, v):
        self._setvalue('_value', v, 'value')

    def clone(self):
        return associationsmapping(self.name, self.associations, self.derived)

class entitiesmapping(mapping):
    def __init__(self, name, es):
        self.entities = es
        self._value = None
        super().__init__(name)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._setvalue('_value', v, 'value')

    def clone(self):
        return entitiesmapping(self.name, self.entities)

class entitymapping(mapping):
    def __init__(self, name, e, derived=False):
        self.entity = e
        self._value = None
        super().__init__(name, derived)

    @property
    def value(self):
        if not self._value:
            for map in self.orm.mappings:
                if type(map) is foreignkeyfieldmapping:
                    if map.entity is self.entity:
                        if map.value not in (undef, None):
                            self._value = self.entity(map.value)
        return self._value

    @value.setter
    def value(self, v):
        self._setvalue('_value', v, 'value')

    def clone(self):
        return entitymapping(self.name, self.entity, derived=self.derived)

class aggregateindexes(entitiesmod.entities):
    pass

class aggregateindex(entitiesmod.entity):
    def __init__(self):
        self.indexes = indexes()

    @property
    def name(self):
        return self.indexes.first.name

    @property
    def isfulltext(self):
        return type(self.indexes.first) is fulltext

    def __str__(self):
        self.indexes.sort('ordinal')

        ixtype = 'FULLTEXT' if self.isfulltext else 'INDEX'
        r = '%s %s (' % (ixtype ,self.name)
        for i, ix in enumerate(self.indexes):
            r += (', ' if i else '') + ix.map.name

        r += ')'

        return r
            
class indexes(entitiesmod.entities):
    pass

class index(entitiesmod.entity):
    def __init__(self, name=None, ordinal=None):
        self._name = name
        self.ordinal = ordinal
        self.map = None

    @property
    def name(self):
        name = self._name if self._name else self.map.name

        name = name if name.endswith('_ix') else name + '_ix'

        return name

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return super().__repr__() + ' ' + self.name

class fulltexts(indexes):
    pass

class fulltext(index):
    @property
    def name(self):
        name = self._name if self._name else self.map.name

        name = name if name.endswith('_ftix') else name + '_ftix'

        return name

class attr:
    class wrap:
        def __init__(self, *args, **kwargs):
            args = list(args)
            self.fget = args.pop()
            self.args = args
            self.kwargs = kwargs

        @property
        def mapping(self):
            map = fieldmapping(*self.args, **self.kwargs)
            map.isexplicit = True
            return map

        def __get__(self, e, etype=None):
            name = self.fget.__name__
            def attr(v=undef):
                if v is undef:
                    try:
                        return e.orm.mappings[name].value
                    except IndexError:
                        # If it's not in the subentity's mapping collection,
                        # make a regular getattr() call on e's super. 
                        super = e.orm.super
                        if super:
                            return getattr(super, name)
                else:
                    e.__setattr__(name, v, cmp=False)
                    return v

            self.fget.__globals__['attr'] = attr
            # FIXME If an AttributeError is raised in the fget invocation, it
            # is ignored for some reason. Though counterintuitive, some
            # information may be here to help explain why:
            # https://stackoverflow.com/questions/50542177/correct-handling-of-attributeerror-in-getattr-when-using-property
            return self.fget(e)

    def __init__(self, *args, **kwargs):
        self.args = list(args)
        self.kwargs = kwargs

    def __call__(self, meth):
        self.args.append(meth)
        w = attr.wrap(*self.args, **self.kwargs)
        return w

class fieldmapping(mapping):
    # Permitted types
    types = bool, str, int, float, decimal.Decimal, bytes, datetime
    def __init__(self, type,       # Type of field
                       min=None,   # Max length or size of field
                       max=None,   # Min length or size of field
                       m=None,     # Precision (in decimals and floats)
                       d=None,     # Scale (in decimals and floats)
                       name=None,  # Name of the field
                       ix=None,    # Database index
                       derived=False,
                       isexplicit=False):

        if type in (float, decimal.Decimal):
            if min is not None:
                m, min = min, None
            if max is not None:
                d, max = max, None
        
        self._type       =  type
        self._value      =  undef
        self._min        =  min
        self._max        =  max
        self._precision  =  m
        self._scale      =  d
        self.isexplicit  =  isexplicit

        # TODO Currently, a field is limited to being part of only one
        # composite or fulltext index. This code could be improved to allow for
        # multiple indexes per fieldmapping.

        if ix is not None                and \
           isinstance(ix, builtins.type) and \
           index in ix.mro():

            self._ix = ix()
        else:
            self._ix = ix

        if self.index:
            self.index.map = self

        super().__init__(name, derived)

    def clone(self):
        ix = self.index
        ix = index(name=ix.name, ordinal=ix.ordinal) if ix else None

        map = fieldmapping(
            self.type,
            self.min,
            self.max,
            self.precision,
            self.scale,
            self.name,
            ix,
            self.derived,
            self.isexplicit
        )

        if ix:
            ix.map = map

        map._value = self._value

        return map

    @property
    def index(self):
        return self._ix

    @property
    def isstr(self):
        return self.type == types.str

    @property
    def isdatetime(self):
        return self.type == types.datetime

    @property
    def isbool(self):
        return self.type == types.bool

    @property
    def isint(self):
        return self.type == types.int

    @property
    def isfloat(self):
        return self.type == types.float

    @property
    def isdecimal(self):
        return self.type == types.decimal

    @property
    def isbytes(self):
        return self.type == types.bytes

    @property
    def isfixed(self):
        if self.isint or self.isfloat or self.isdecimal:
            return True

        if self.isbytes or self.isstr:
            return self.max == self.min
        return False

    @property
    def min(self):
        if self.isstr:
            if self._min is None:
                return 1

        elif self.isint:
            if self._min is None:
                return -2147483648

        elif self.isfloat:
            if self._min is None:
                return -self.max
            else:
                return float(self._min)

        elif self.isdecimal:
            if self._min is None:
                return -self.max
            else:
                return decimal.Decimal(self._min)

        elif self.isdatetime:
            ... # TODO?
        elif self.isbytes:
            ... # TODO?

        return self._min

    @property
    def precision(self):
        if not (self.isfloat or self.isdecimal):
            return None

        if self._precision is None:
            return 12

        return self._precision

    @property
    def scale(self):
        if not (self.isfloat or self.isdecimal):
            return None

        if self._scale is None:
            return 2

        return self._scale
        
    @property
    def max(self):
        t = self.type
        if self.isstr:
            if self._max is None:
                return 255
            else:
                return self._max

        elif self.isint:
            if self._max is None:
                return 2147483647
            else:
                return self._max

        elif self.isfloat or self.isdecimal:
            m, d = self.precision, self.scale
            str = '9' * m
            str = '%s.%s' % (str[:m-d], str[:d])
            return float(str) if self.isfloat else decimal.Decimal(str)

        elif t is types.bytes:
            if self._max is None:
                return 255
            return self._max

    @property
    def type(self):
        t = self._type
        if t in (str, types.str):
            return types.str
        elif t in (int, types.int):
            return types.int
        elif t in (bool, types.bool):
            return types.bool
        elif hasattr(t, '__name__') and t.__name__ == 'datetime':
            return types.datetime
        elif t in (float,):
            return types.float
        elif hasattr(t, '__name__') and t.__name__.lower() == 'decimal':
            return types.decimal
        elif t in (bytes,):
            return types.bytes
        return self._type

    @property
    def signed(self):
        if self.type not in (types.int, types.float, types.decimal):
            raise ValueError()

        return self.min < 0
    
    @property
    def dbtype(self):
        if self.isstr:
            if self.max <= 65535:
                if self.isfixed:
                    return 'char(' + str(self.max) + ')'
                else:
                    return 'varchar(' + str(self.max) + ')'
            else:
                return 'longtext'

        elif self.isint:
            if self.min < 0:
                if    self.min  >=  -128         and  self.max  <=  127:
                    return 'tinyint'
                elif  self.min  >=  -32768       and  self.max  <=  32767:
                    return 'smallint'
                elif  self.min  >=  -8388608     and  self.max  <=  8388607:
                    return 'mediumint'
                elif  self.min  >=  -2147483648  and  self.max  <=  2147483647:
                    return 'int'
                elif  self.min  >=  -2**63       and  self.max  <=  2**63-1:
                    return 'bigint'
                else:
                    raise ValueError()
            else:
                if self.max  <=  255:
                    return 'tinyint unsigned'
                elif self.max  <=  65535:
                    return 'smallint unsigned'
                elif self.max  <=  16777215:
                    return 'mediumint unsigned'
                elif self.max  <=  4294967295:
                    return 'int unsigned'
                elif self.max  <=  (2 ** 64) - 1:
                    return 'bigint unsigned'
                else:
                    raise ValueError()
        elif self.isdatetime:
            return 'datetime(6)'
        elif self.isbool:
            return 'bit'
        elif self.isfloat:
            return 'double(%s, %s)' % (self.precision, self.scale)
        elif self.isdecimal:
            return 'decimal(%s, %s)' % (self.precision, self.scale)
        elif self.isbytes:
            if self.isfixed:
                return 'binary(%s)' % self.max
            else:
                return 'varbinary(%s)' % self.max
        else:
            raise ValueError()

    @property
    def value(self):
        if self._value is undef:
            if self.isint:
                return int()
            elif self.isbool:
                return bool()
            elif self.isfloat:
                return float()
            elif self.isdecimal:
                return decimal.Decimal()
            elif self.isstr:
                return str()
            elif self.isbytes:
                return bytes()
            else:
                return None
        
        if self._value is not None:
            if self.isstr:
                try:
                    self._value = str(self._value)
                except:
                    pass

            elif self.isdatetime:
                try:
                    if type(self._value) is str:
                        self._value = primative.datetime(self._value) 
                    elif not isinstance(self._value, primative.datetime):
                        self._value = primative.datetime(self._value)
                except:
                    pass
                else:
                    utc = dateutil.tz.gettz('UTC')
                    if self._value.tzinfo and self._value.tzinfo is not utc:
                        self._value = self._value.astimezone(utc)
                    else:
                        self._value = self._value.replace(tzinfo=utc)
            elif self.isbool:
                if type(self._value) is bytes:
                    # Convert the bytes string fromm MySQL's bit type to a
                    # bool.
                    v = self._value
                    self._value = bool.from_bytes(v, byteorder='little')

            elif self.isint:
                try:
                    self._value = int(self._value)
                except:
                    pass
            elif self.isfloat:
                try:
                    self._value = round(float(self._value), self.scale)
                except:
                    pass

            elif self.isdecimal:
                try:
                    d = decimal.Decimal(str(self._value))
                except:
                    pass
                else:
                    self._value = round(d, self.scale)

            elif self.isbytes:
                try:
                    self._value = bytes(self._value)
                except:
                    pass

        return self._value

    @value.setter
    def value(self, v):
        self._value = v

class foreignkeyfieldmapping(fieldmapping):
    def __init__(self, e, derived=False):
        self.entity = e
        self.value = None
        super().__init__(type=types.fk, derived=derived)

    @property
    def name(self):
        return self.entity.__name__ + 'id'

    def clone(self):
        return foreignkeyfieldmapping(self.entity, self.derived)

    @property
    def dbtype(self):
        return 'binary(16)'

    @property
    def value(self):
        if type(self._value) is bytes:
            self._value = UUID(bytes=self._value)
            
        return self._value

    @value.setter
    def value(self, v):
        self._value = v

class primarykeyfieldmapping(fieldmapping):
    def __init__(self):
        super().__init__(type=types.pk)

    @property
    def name(self):
        return 'id'

    def clone(self):
        return primarykeyfieldmapping()

    @property
    def dbtype(self):
        return 'binary(16) primary key'

    @property
    def value(self):
        # If a super instance exists, use that because we want a subclass and
        # its super class to share the same id. Here we use ._super instead of
        # .super because we don't want the invoke the super accessor because it
        # calls the id accessor (which calls this accessor). This leads to
        # infinite recursion. This, of course, assumes that the .super accessor
        # has previously been called.

        super = self.orm._super
        if super:
            return super.id

        if type(self._value) is bytes:
            self._value = UUID(bytes=self._value)
            
        return self._value

    @value.setter
    def value(self, v):
        self._value = v

class ormclasseswrapper(entitiesmod.entities):
    def append(self, obj, uniq=False, r=None):
        if isinstance(obj, type):
            obj = ormclasswrapper(obj)
        elif isinstance(obj, ormclasswrapper):
            pass
        else:
            raise ValueError()
        super().append(obj, uniq, r)
        return r

class ormclasswrapper(entitiesmod.entity):
    def __init__(self, entity):
        self.entity = entity
        super().__init__()

    def __str__(self):
        return str(self.entity)

    def __repr__(self):
        return repr(self.entity)

    def __getattr__(self, attr):
        return getattr(self.entity, attr)

    @property
    def orm(self):
        return self.entity.orm

    @property
    def name(self):
        return self.entity.__name__

class composites(ormclasseswrapper):
    pass

class composite(ormclasswrapper):
    pass

class constituents(ormclasseswrapper):
    pass

class constituent(ormclasswrapper):
    pass

class orm:
    def __init__(self):
        self.mappings             =  None
        self.isnew                =  False
        self._isdirty             =  False
        self.ismarkedfordeletion  =  False
        self.entities             =  None
        self.entity               =  None
        self.table                =  None
        self._composits           =  None
        self._constituents        =  None
        self._associations        =  None
        self._trash               =  None
        self._subclasses          =  None
        self._super               =  None
        self._base                =  undef
        self.instance             =  None
        self.stream               =  None
        self.isloaded             =  False
        self.isloading            =  False
        self.isremoving           =  False
        self.joins                =  None

    def clone(self):
        r = orm()

        props = (
            'isnew',       '_isdirty',     'ismarkedfordeletion',
            'entity',      'entities',     'table'
        )

        for prop in props: 
            setattr(r, prop, getattr(self, prop))

        r.mappings = self.mappings.clone(r)

        return r

    def populate(self, res):
        ''' Given a dbresultset object, iterate over each of the fields objects
        to populate the object's map values. If nested fields names are
        encounted ('parent.child.id'), the graph is searched recursively until
        the leaf object is found and its fields are populated with the field
        value. '''

        prevnodes = None
        for f in res.fields:
            # The field.name proprety is assumed to be a graph description
            # (e.g., 'grandparent.parent.child.id'). Call the first part
            # 'nodes' and the second part col.
            nodes = f.name.split('.')[1:]
            col = nodes.pop()

            # If there are no nodes, we must be at the root, so set 'map' and it
            # will be assigned after conditional.
            if len(nodes) == 0:
                map = self.mappings[col]
            else:

                # If graph has changed
                if nodes != prevnodes:

                    # Only need to do this once for each graph
                    if col != 'id':
                        continue

                    # Go through each node in nodes. The goal is to drill down
                    # the graph until we find the leaf object. Then instantiate
                    # the leaf object and assign it to the correct entities
                    # collection object.
                    maps = self.mappings
                    for i, node in enumerate(nodes):
                        map = maps[node]

                        # Get the entities collection. Create it if it doesn't
                        # yet exist.
                        if map.value:
                            es = map.value
                        else:
                            es = map.entities()
                            map.value = es

                        # If last node
                        if i + 1 == len(nodes):
                            # Prevent duplicate entries to an entities
                            # collection.
                            # TODO Tighten up by overridding the |= to prevent
                            # duplicates based on entitiy's id a value
                            dup = False
                            for e in es:
                                if e.id == UUID(bytes=f.value):
                                    dup = True
                                    break
                            else:
                                e = map.entities.orm.entity()
                                es += e

                        maps = e.orm.mappings
                            
                # Now that we have the correct maps collection, we can get the
                # map by indexing it off the column name.
                map = maps[col]

            # Assign the field value (from the db), to the map. 
            map.value = f.value
            prevnodes = nodes

        self.isnew = False
        self.isdirty = False
    
    # TODO Is depth being used
    def getselects(self, depth=0, rentjoin=None):
        R = table(border=None)

        for map in self.entity.orm.mappings:
            if not isinstance(map, fieldmapping):
                continue
            r = R.newrow()
            # FIXME: Aliases can only be 256 chars long. This recursive
            # algorithm chains aliase names togethr such that a deeply nested
            # join may eventually exceed that limit.  A fix would be for entity
            # classes to create unique abbreviations for themselves 
            #
            # assert artist.orm.abbreviation == 'ar'
            #
            # The abbreviations can be used in place of the table names in the
            # aliase.  This should make virtually any sane, deeply-nested join
            # possible.
            r.newfields(map.fullname, 'AS', map.fullname, ',')

        tbl = self.table
        for join in self.joins:
            e = join.entities.orm.entity
            orm = join.entities.orm
            for row in orm.getselects(depth=depth + 1, rentjoin=join):
                fs = [str(f) for f in row]
                r = R.newrow()

                f1 = alias = '%s.%s' % (tbl, fs[2])
                r.newfields(f1, 'AS', alias, ',')

        r.fields.pop() # Pop the trailing comma

        if not depth:
            for r in R:
                graph, col = r.fields[0].value.rsplit('.', 1)
                r.fields[0].value = '`%s`.%s' % (graph, col)
                r.fields[2].value = '`%s`' % r.fields[2].value
                
        return R

    @property
    def selects(self):
        return self.getselects()

    def getwhere(self):
        ''' Return a string representation of the WHERE clause with %s
        parameters. If the where object's entities collection has joins, those
        joins will be traversed to captures all where clauses. '''

        # Start off with a 'WHERE '
        r = 'WHERE '

        args = []

        # Concatentate the predicate with graph to return string
        graph = self.entities.orm.table
        wh = self.where
        if wh:
            r += '(%s)' % wh.predicate.__str__(columnprefix=graph)
            args += wh.args


        # Recursively join `where` predicates into the return variable.
        # Recursions can happen via this join() function, or, if a `where'
        # object is available on the `join` object, a call to the `where`'s
        # __str__ method will result in recursion instead.

        def concatenate(js, graph):
            nonlocal r, args
            for j in js:
                tbl = j.entities.orm.table
                graph1 = ('%s.%s') % (graph, tbl) if graph else tbl
                if j.where:
                    # If a join object has a where, use it's where to stringify the
                    # predicate.

                    # Recurse into the join's where's __str__ passing in graph
                    p = '\n AND (%s)'
                    p %= j.where.predicate.__str__(columnprefix=graph1)
                    r += p
                    args += j.where.args

                concatenate(j.entities.orm.joins, graph1)

        # Call join with this where objects entities' joins
        concatenate(self.joins, graph)

        return r, args

    @property
    def sql(self):
        ''' Returns the SELECT statement needed to load an entities collection.
        The SELECT takes into account JOINs, WHERE clauses, WHERE arguments and
        ORDER BY clauses (when streaming). '''

        # SELECT
        select = textwrap.indent(str(self.selects), ' ' * 4)

        sql = 'SELECT \n%s\nFROM %s\n' % (select, self.table)

        # JOINs.
        if self.joins.count:
            joins = str(self.joins) 
        else:
            joins = None

        sql += joins if joins else ''
        
        # WHERE
        wh = self.where
        #sql += str(self.where)
        wh, args = self.getwhere()
        sql += wh

        # ORDER BY
        if self.isstreaming:
            if self.stream.orderby:
                sql += ' ORDER BY ' + self.stream.orderby
        
        # Return the SQL followed by the args from the WHERE object. Note that the 
        # str(self.where) and self.where.args, though being recursive, will ensure 
        # that the placeholders (%s) and the arguments occure in the same order.
        return sql, args

    @staticmethod
    def introduce(sql, args):
        """Use args to add introducers (_binary, et. al.) before the %s in
        sql."""

        # Where the arg is binary (bytearray or bytes), replace '%s' with
        # '_binary %s' so it's clear to MySQL where the UTF8 SQL string 
        # becomes pure binary not intended for character decoding.
        return sql % tuple(
            [
                '_binary %s' if type(x) in (bytearray, bytes) else '%s' 
                for x in args
            ]
        )

    @property
    def isstreaming(self):
        return self.stream is not None

    @property
    def isdirty(self):
        if self._isdirty:
            return True

        if self.super:
            return self.super.orm.isdirty

        return False

    @isdirty.setter
    def isdirty(self, v):
        self._isdirty = v

    @property
    def forentities(self):
        return isinstance(self.instance, entities)
        
    @property
    def forentity(self):
        return isinstance(self.instance, entity)

    @property
    def persistencestates(self):
        es = self.instance
        if not self.forentities:
            msg = 'Use with entities. For entity, use persistencestate'
            raise ValueError(msg)
            
        sts = []
        for e in es:
            sts.append(e.orm.persistencestate)
        return sts

    @persistencestates.setter
    def persistencestates(self, sts):
        es = self.instance
        if not self.forentities:
            msg = 'Use with entities. For entity, use persistencestate'
            raise ValueError(msg)

        for e, st in zip(es, sts):
            e.orm.persistencestate = st

    @property
    def persistencestate(self):
        es = self.instance
        if not self.forentity:
            msg = 'Use with entity. For entities, use persistencestates'
            raise ValueError(msg)
        return self.isnew, self.isdirty, self.ismarkedfordeletion

    @persistencestate.setter
    def persistencestate(self, v):
        es = self.instance
        if not isinstance(es, entity):
            msg = 'Use with entity. For entities, use persistencestates'
            raise ValueError(msg)
        self.isnew, self.isdirty, self.ismarkedfordeletion = v

    @property
    def trash(self):
        if not self._trash:
            self._trash = self.entities()
        return self._trash

    @trash.setter
    def trash(self, v):
        self._trash = v

    @property
    def properties(self):
        props = [x.name for x in self.mappings]

        for map in self.mappings.associationsmappings:
            for map1 in map.associations.orm.mappings.entitymappings:
                if self.entity is not map1.entity:
                    props.append(map1.entity.orm.entities.__name__)


        super = self.super
        if super:
            props += [x for x in super.orm.properties if x not in props]

        return props

    @staticmethod
    def getsubclasses(of):
        r = []

        for sub in of.__subclasses__():
            if sub not in (associations, association):
                r.append(sub)
            r.extend(orm.getsubclasses(sub))

        return r

    @staticmethod
    def issub(obj1,  obj2):
        if not (isinstance(obj1, type) and isinstance(obj2, type)):
            msg = 'Only static types are currently supported'
            raise NotImplementedError(msg)

        cls1, cls2 = obj1, obj2

        super = cls2

        while super:
            if super is cls1:
                return True
            super = super.orm.super

        return False
        

    @property
    def super(self):
        """ For orms that have no instance, return the super class of
        orm.entity.  If orm.instance is not None, return an instance of that
        objects super class.  A super class here means the base class of of an
        entity class where the base itself is not entity, but rather a subclass
        of entity. So if class A inherits directly from entity, it will have a
        super of None. However if class B inherits from A. class B will have a
        super of A."""
        if self._super:
            return self._super

        if self._base is not undef:
            return self._base

        if self.entity:
            bases = self.entity.__bases__
            try:
                base = bases[0]
            except IndexError:
                base = None

            if base in (entity, association):
                self._base = None
                return self._base

            if self.isstatic:
                self._base = base
                return self._base

            elif self.isinstance:
                if self.isnew:
                    self._super = base()
                else:
                    e = self.instance
                    if not isinstance(e, entity):
                        msg = "'super' is not an attribute of %s"
                        msg %= str(type(e))
                        raise AttributeError(msg)
                    if e.id is not undef:
                        self._super = base(e.id)

                return self._super

        return None

    @property
    def isstatic(self):
        return self.instance is None

    @property
    def isinstance(self):
        return self.instance is not None

    @property
    def subclasses(self):
        if self._subclasses is None:
            clss = ormclasseswrapper()
            for sub in orm.getsubclasses(of=self.entity):
                clss += sub
            self._subclasses = clss
        return self._subclasses
        
    @staticmethod
    def getassociations():
        return orm.getsubclasses(of=association)

    @staticmethod
    def getentitys():
        r = []
        for e in orm.getsubclasses(of=entity):
            if association not in e.mro():
                if e is not association:
                    r += [e]
        return r

    @property
    def associations(self):
        if not self._associations:
            self._associations = ormclasseswrapper()
            for ass in orm.getassociations():
                for map in ass.orm.mappings.entitymappings:
                    if map.entity is self.entity:
                        self._associations += ormclasswrapper(ass)

        return self._associations
            
    @property
    def composites(self):
        if not self._composits:
            self._composits = composites()
            for sub in self.getsubclasses(of=entity):
                for map in sub.orm.mappings.entitiesmappings:
                    if map.entities.orm.entity is self.entity:
                        self._composits += composite(sub)
                        break

            for ass in self.getassociations():
                maps = list(ass.orm.mappings.entitymappings)
                for i, map in enumerate(maps):
                    if orm.issub(map.entity, self.entity):
                        e = maps[int(not bool(i))].entity
                        self._composits += composite(e)
                        break
                else:
                    continue
                break

        return self._composits

    @property
    def constituents(self):
        if not self._constituents:
            self._constituents = constituents()
            for map in self.mappings.entitiesmappings:
                e = map.entities.orm.entity
                self._constituents += constituent(e)

            for ass in self.getassociations():
                maps = list(ass.orm.mappings.entitymappings)
                for i, map in enumerate(maps):
                    if map.entity is self.entity:
                        e = maps[int(not bool(i))].entity
                        self._constituents += constituent(e)
                        break
                else:
                    continue
                break
        return self._constituents

class saveeventargs(entitiesmod.eventargs):
    def __init__(self, e):
        self.entity = e

class associations(entities):
    def __init__(self, *args, **kwargs):
        # TODO Why do associations have composite and _constituents have
        # properties.  Shouldn't these be behind the associations' orm
        # property, i.e., asses.orm.composite, etc.
        self.composite = None
        self._constituents = {}
        super().__init__(*args, **kwargs)

    def append(self, obj, uniq=False, r=None):
        if isinstance(obj, association):
            for map in obj.orm.mappings.entitymappings:
                # TODO We probably should be using the association's (self) mappings
                # collection to test the composites names. The name that matters is
                # on the LHS of the map when being defined in the association class.
                if map.name == type(self.composite).__name__:
                    setattr(obj, map.name, self.composite)
                    break;
            
        super().append(obj, uniq, r)
        return r

    def _self_onremove(self, src, eargs):
        """ This event handler occures when an association is removed from an
        assoctions collection. When this happens, we want to remove the
        association's constituent entity (the non-composite entity) from its
        pseudocollection class - but only if it hasn't already been marked for
        deletion (ismarkedfordeletion). If it has been marked for deletion,
        that means the psuedocollection class is invoking this handler - so
        removing the constituent would result in infinite recursion.  """

        ass = eargs.entity

        for i, map in enumerate(ass.orm.mappings.entitymappings):
            if map.entity is not type(self.composite):
                e = map.value
                if not e.orm.ismarkedfordeletion:
                    es = getattr(self, e.orm.entities.__name__)
                    es.remove(e)
                    break
            
        super()._self_onremove(src, eargs)

    def entities_onadd(self, src, eargs):
        ass = None
        for map in self.orm.mappings.entitymappings:
            if map.entity is type(eargs.entity):
                for ass in self:
                    if getattr(ass, map.name) is eargs.entity:
                        # eargs.entity already exists as a constitutent entity
                        # in this collection of associations. There is no need
                        # to add it again.
                        return

                ass = self.orm.entity()
                setattr(ass, map.name, eargs.entity)
            if map.entity is type(self.composite):
                compmap = map
        
        setattr(ass, compmap.name, self.composite)
        self += ass

    def entities_onremove(self, src, eargs):
        for map in self.orm.mappings.entitymappings:
            if map.entity is type(eargs.entity):
                for ass in self:
                    if getattr(ass, map.name) is eargs.entity:
                        break
                else:
                    continue
                break
        else:
            return

        self.remove(ass)

    def __getattr__(self, attr):
        # TODO Use the mappings collection to get __name__'s value.
        if attr == type(self.composite).__name__:
            return self.composite

        try:
            return self._constituents[attr]
        except KeyError:
            for map in self.orm.mappings.entitymappings:
                es = map.entity.orm.entities
                if es.__name__ == attr:
                    es = es()
                    es.onadd    += self.entities_onadd
                    es.onremove += self.entities_onremove
                    self._constituents[attr] = es
                    break
            else:
                raise AttributeError('Entity not found')

            for ass in self:
                es += getattr(ass, map.name)

        return self._constituents[attr]
    
class association(entity):
    @classmethod
    def reCREATE(cls, cur, recursive=False, clss=None):
        for map in cls.orm.mappings.entitymappings:
            map.entity.reCREATE(cur, recursive, clss)

        super().reCREATE(cur, recursive, clss)
