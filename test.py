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
from articles import *
from parties import *
from configfile import configfile
from entities import brokenruleserror
from MySQLdb.constants.ER import BAD_TABLE_ERROR, DUP_ENTRY
from pdb import set_trace; B=set_trace
from tester import *
from uuid import uuid4
import MySQLdb
import re

class test_blog(tester):
    def __init__(self):
        super().__init__()
        blogs().RECREATE()

    def it_creates(self):
        bl = blog()
        bl.slug = 'carapacian-tech'
        bl.description = "The technical blog for Carapacian, LLC"
        self.assertTrue(bl._isnew)
        self.assertFalse(bl._isdirty)
        self.assertNone(bl.id)
        bl.save()
        self.assertTrue(type(bl.id) == uuid.UUID)
        self.assertFalse(bl._isnew)
        self.assertFalse(bl._isdirty)

        bl1 = blog(bl.id)

        self.assertFalse(bl1._isnew)
        self.assertFalse(bl1._isdirty)
        self.assertEq(bl.id, bl1.id)
        self.assertEq(bl.slug, bl1.slug)
        self.assertEq(bl.description, bl1.description)

    def it_sets_properties(self):
        slug = 'carapacian-tech'
        description = "The technical blog for Carapacian, LLC"
        bl = blog()
        bl.slug = slug
        bl.description = description
        self.assertEq(slug, bl.slug)
        self.assertEq(description, bl.description)

    def it_breaks_rules(self):
        slug = 'carapacian-tech'
        description = "The technical blog for Carapacian, LLC"
        bl = blog()
        self.assertCount(2, bl.brokenrules)
        self.assertTrue(bl.brokenrules.contains('slug', 'full'))
        self.assertTrue(bl.brokenrules.contains('description', 'full'))
        bl.slug = slug
        self.assertCount(1, bl.brokenrules)
        self.assertTrue(bl.brokenrules.contains('description', 'full'))
        bl.description = description
        self.assertCount(0, bl.brokenrules)

    def it_updates(self):
        slug = str(uuid4())
        description = "The technical blog for Carapacian, LLC"
        bl = blog()
        bl.slug = slug
        bl.description = description
        bl.save()

        bl = blog(bl.id)
        bl.description = 'new'
        bl.save()

        bl = blog(bl.id)
        self.assertEq('new', bl.description)
        self.assertEq(slug, bl.slug)

        slug = str(uuid4())
        bl.slug = slug
        bl.save()

        bl = blog(bl.id)
        self.assertEq('new', bl.description)
        self.assertEq(slug, bl.slug)

    def it_loads_as_valid(self):
        bl = blog()
        bl.slug = str(uuid4())
        bl.description = "The technical blog for Carapacian, LLC"
        bl.save()
        self.assertValid(blog(bl.id))

    def it_violates_unique_constraint_on_slug(self):
        bl = blog()
        bl.slug = 'non-unique'
        bl.description = "The technical blog for Carapacian, LLC"
        bl.save()

        bl = blog()
        bl.slug = 'non-unique'
        bl.description = "The technical blog for Carapacian, LLC"
        try:
            bl.save()
        except MySQLdb.IntegrityError as ex:
            self.assertTrue(ex.args[0] == DUP_ENTRY)
        except Exception:
            self.assertFail('Wrong exception')
        else:
            self.assertFail("Didn't raise IntegrityError")

class test_blogpostrevision(tester):
    def __init__(self):
        super().__init__()
        articlerevisions().RECREATE()
        blogpostrevisions().RECREATE()
        blogs().RECREATE()

        # Create a blog
        bl = blog()
        bl.slug = 'carapacian-tech-blog'
        bl.description = 'Carapacian Tech Blog'
        bl.save()

        self.blog = bl

    def it_creates(self):
        bl = self.blog

        # Create blogpostrevision
        body = test_blogpost.Smallpostbody
        title = test_article.Smallposttitle + ' - ' + str(uuid4())
        slug = re.sub(r'\W+', '-', title).strip('-').lower()

        rev = blogpostrevision()
        rev.title = title
        rev.body = body
        rev.blog = bl
        rev.slug = slug
        rev.excerpt = test_article.Smallpostexcerpt
        rev.status = article.Pending
        rev.iscommentable = False
        rev.slug_cache = slug
        rev.save()

        # Reload blogpostrevision and test
        rev1 = blogpostrevision(rev.id)
        self.assertEq(rev.title, rev1.title)
        self.assertEq(rev.slug, rev1.slug)
        self.assertEq(rev.body, rev1.body)
        self.assertEq(rev.excerpt, rev1.excerpt)
        self.assertEq(rev.status, rev1.status)
        self.assertEq(rev.iscommentable, rev1.iscommentable)
        self.assertEq(rev.slug_cache, rev1.slug_cache)
        self.assertEq(bl.id, rev1.blog.id)

    def it_instantiates(self):
        rev = blogpostrevision()
        self.assertNone(rev.id)
        self.assertNone(rev.authors)
        self.assertNone(rev.created_at)
        self.assertNone(rev.title)
        self.assertNone(rev.body)
        self.assertNone(rev.excerpt)
        self.assertEq(article.Draft, rev.status)
        self.assertFalse(rev.iscommentable)
        self.assertNone(rev.slug)
        self.assertNone(rev.blog)

    def it_fails_on_save_when_invalid(self):
        rev = blogpostrevision()
        try:
            rev.save()
        except brokenruleserror as ex:
            self.assertIs(rev, ex.object)
        except Exception as ex:
            msg = ('brokenruleserror expected however a different exception '
                  ' was thrown: ' + str(type(ex)))
            self.assertFail(msg)
        else:
            self.assertFail('No exception thrown on save of invalid object.')

    def it_fails_to_load_given_nonexistent_id(self):
        try:
            rev = blogpostrevision(uuid4())
        except Exception as ex:
            self.assertTrue(True)
        else:
            self.assertFail('Exception was not thrown')

    def it_loads_as_valid(self):
        rev = blogpostrevision()
        rev.body = test_blogpost.Smallpostbody
        rev.title = test_article.Smallposttitle + str(uuid4())
        rev.blog = self.blog
        rev.save()

        rev = blogpostrevision(rev.id)
        self.assertValid(rev)

    def it_breaks_diff_rules(self):
        # Diff must be empty for root revisions
        rev = blogpostrevision()
        rev.body = test_blogpost.Smallpostbody
        rev.title = test_article.Smallposttitle
        rev.diff = diff.diff('herp', 'derp')
        rev.blog = self.blog
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('diff', 'empty'))

        # Fix
        rev.diff = None
        self.assertValid(rev)

        # Break the rule that says a diff must be of type diff.diff
        rent = blogpostrevision()
        rent.body = test_blogpost.Smallpostbody
        rent.title = test_article.Smallposttitle
        rev.blog = self.blog
        rent.diff = diff.diff('herp', 'derp')

        rev._parent = rent
        rev.body = None
        rev.diff = 'wrong type'
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('diff', 'valid'))

    def it_breaks_title_rules(self):
        # Root revisions must have non null titles
        rev = blogpostrevision()
        rev.body = test_blogpost.Smallpostbody
        rev.blog = self.blog
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('title', 'full'))

        # Non-root revisions can have null titles
        rev._parent = blogpostrevision()
        self.assertCount(0, rev.brokenrules)

        # Root revisions can have empty strings as titles
        rev = blogpostrevision()
        rev.body = test_blogpost.Smallpostbody
        rev.blog = self.blog
        rev.title = ''
        self.assertCount(0, rev.brokenrules)

        # Revisions titles must be strings
        rev.title = 123
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('title', 'valid'))
        rev._parent = blogpostrevision() # Make non-root
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('title', 'valid'))

        # Title must be less than 500 characters
        rev = blogpostrevision()
        rev.blog = self.blog
        rev.body = test_blogpost.Smallpostbody
        rev.title = 'X' * 500
        self.assertCount(0, rev.brokenrules)
        rev.title = 'X' * 501
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('title', 'fits'))

    def it_breaks_status_rules(self):
        rev = blogpostrevision()
        rev.blog = self.blog
        rev.body = test_blogpost.Smallpostbody
        rev.title = test_article.Smallposttitle
        for st in article.Statuses:
            rev.status = st
            self.assertCount(0, rev.brokenrules)

        for st in ('wrong-type', 9999, object()):
            rev.status = st
            self.assertCount(1, rev.brokenrules)
            self.assertTrue(rev.brokenrules.contains('status', 'valid'))

    def it_breaks_body_rules_of_child(self):
        rent = blogpostrevision()
        rent.body = test_blogpost.Smallpostbody
        rent.title = test_article.Smallposttitle + str(uuid4())
        rent.blog = self.blog
        self.assertValid(rent)

        rev = blogpostrevision()
        rev._parent = rent
        rev.body = None
        rev.diff = diff.diff(rent.body, rent.body + '\n<b>This is strong</strong>')
        self.assertTrue(rev.brokenrules.contains('derivedbody', 'valid'))

    def it_breaks_body_rules(self):
        # Body must be full for root revisions
        rev = blogpostrevision()
        rev.blog = self.blog
        self.assertCount(2, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('body', 'full'))
        self.assertTrue(rev.brokenrules.contains('title', 'full'))

        # Invalid HTML in body
        rev.body = '<em>This is special</i>'
        self.assertCount(2, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('body', 'valid'))

        # Create a parent then test the child
        rent = blogpostrevision()
        rent.body = test_blogpost.Smallpostbody
        rent.title = test_article.Smallposttitle
        rent.diff = diff.diff('herp', 'derp')

        # A body and a diff shouldn't exist in the same record
        rev._parent = rent
        rev.diff = diff.diff('herp', 'derp')
        rev.body = test_blogpost.Smallpostbody
        self.assertCount(2, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('diff', 'valid'))

        # A non-root revision should can have a body but no diff. This
        # may be useful for caching or other isssues such as a failure to
        # create a diff.
        rev.body = test_blogpost.Smallpostbody
        rev.diff = None
        self.assertValid(rev)
    
    def it_breaks_blog_rules(self):
        # Body must be full for root revisions
        rev = blogpostrevision()
        rev.body = test_blogpost.Smallpostbody
        rev.title = test_article.Smallposttitle + str(uuid4())
        rev.blog
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('blog', 'full'))

        
    def it_retrieves(self):
        rev = blogpostrevision()
        rev.blog = self.blog
        rev.body = test_article.Smallpostbody
        rev.title = test_article.Smallposttitle + str(uuid4())
        rev.save()
        rev = blogpostrevision(rev.id)
        self.assertEq(rev.id, rev.id)

class test_blogpost(tester):
    Smallpostbody = """
    <p>
        But men labor under a mistake. The better part of the man is soon plowed
        into the soil for compost. By a seeming fate, commonly called necessity,
        they are employed, as it says in an old book, laying up treasures which
        moth and rust will corrupt and thieves break through and steal. It is a
        fool's life, as they will find when they get to the end of it, if not
        before. It is said that Deucalion and Pyrrha created men by throwing
        stones over their heads behind them:-
        &nbsp;
    </p>
    <pre xml:space="preserve">           
        Inde genus durum sumus, experiensque laborum,
        Et documenta damus qua simus origine nati.
    </pre>
    <p class="nind">
        Or, as Raleigh rhymes it in his sonorous way,-
    </p>
    <pre xml:space="preserve">  
        "From thence our kind hard-hearted is, enduring pain and care,
        Approving that our bodies of a stony nature are."
    </pre>
    <p class="nind">
        So much for a blind obedience to a blundering oracle, throwing the stones
        over their heads behind them, and not seeing where they fell.
    </p>
    """
    def __init__(self):
        super().__init__()
        articlerevisions().RECREATE()
        blogpostrevisions().RECREATE()
        blogs().RECREATE()

        # Create a blog
        bl = blog()
        bl.slug = 'carapacian-tech-blog'
        bl.description = 'Carapacian Tech Blog'
        bl.save()

        self.blog = bl

    def it_loads_as_valid(self):
        bp = blogpost()
        bp.blog = self.blog
        bp.body = test_article.Smallpostbody
        title = test_article.Smallposttitle + ' - ' + str(uuid4())
        bp.title  = title
        slug = re.sub(r'\W+', '-', bp.title).strip('-').lower()
        bp.excerpt = test_article.Smallpostexcerpt 
        bp.status = article.Pending
        bp.iscommentable = True
        bp.blog = self.blog
        bp.save()

    def it_saves_x_revisions_with_null_properties(self):
        bp = blogpost()
        bp.blog = self.blog
        bp.body = test_article.Smallpostbody
        title = test_article.Smallposttitle + ' - ' + str(uuid4())
        bp.title  = title
        slug = re.sub(r'\W+', '-', bp.title).strip('-').lower()
        bp.excerpt = test_article.Smallpostexcerpt 
        bp.status = blogpost.Pending
        bp.iscommentable = True
        bp.blog = self.blog

        bp.save()

        x = 4
        for i in range(x):
            if i < x / 2:
                bp.title = None
                bp.excerpt = None
                bp.slug = None
            else:
                bp.body = test_article.Smallpostbody  + ' Rev: ' + str(i)
                revisedtitle = title + ' Rev: ' + str(i)
                bp.title = revisedtitle
                bp.excerpt = test_article.Smallpostexcerpt  + ' Rev: ' + str(i)
                
            bp.save()

            bp = blogpost(bp.id)

            if i < x / 2:
                self.assertEq(test_article.Smallpostbody, bp.body)
                self.assertEq(title, bp.title)
                self.assertEq(test_article.Smallpostexcerpt, bp.excerpt)
            else:
                self.assertEq(test_article.Smallpostbody + ' Rev: ' + str(i), bp.body)
                self.assertEq(revisedtitle, bp.title)
                self.assertEq(test_article.Smallpostexcerpt + ' Rev: ' + str(i), bp.excerpt)
            self.assertEq(blogpost.Pending, bp.status)
            self.assertTrue(bp.iscommentable)
            self.assertEq(slug, bp.slug)

    def it_calls_blog(self):
        bp = blogpost()
        self.assertTrue(bp.brokenrules.contains('blog', 'full'))

        self.assertNone(bp.blog)
        bp.blog = self.blog
        self.assertIs(self.blog, bp.blog)

        bp.save()

        bp = blogpost(bp.id)
        bp.blog
        self.assertEq(self.blog.id, bp.blog.id)

    def it_breaks_slug_cache_uniqueness_rule(self):
        bp = blogpost()
        bp.blog = self.blog
        bp.slug = 'my-slug'
        bp.save()

        bp = blogpost()
        bp.blog = self.blog
        bp.slug = 'my-slug'
        self.assertTrue(bp.brokenrules.contains('slug_cache', 'unique'))

        # Create a new blog
        bl = blog()
        bl.slug = 'some-other-tech-blog'
        bl.description = 'Some other blog'
        bl.save()

        bp.blog = bl
        self.assertZero(bp.brokenrules);

    def it_calls_revisions(self):
        # TODO Copy this to test_article
        bp = blogpost()
        bp.blog = self.blog

        self.assertCount(0, bp.revisions)

        # First save
        bp.save()
        self.assertCount(1, bp.revisions)
        self.assertType(blogpostrevisions, bp.revisions)
        for rev in bp.revisions:
            self.assertType(blogpostrevision, rev)

        self.assertEq(bp.blog.id, bp.revisions.first.blog.id)

        # ... then load
        
        bp1 = blogpost(bp.id)
        self.assertCount(1, bp1.revisions)
        self.assertEq(bp1.blog.id, bp1.revisions.first.blog.id)
        self.assertType(blogpostrevisions, bp1.revisions)
        for rev in bp1.revisions:
            self.assertType(blogpostrevision, rev)

        # Second save
        bp.save()
        self.assertCount(2, bp.revisions)
        self.assertEq(bp.blog.id, bp.revisions.first.blog.id)
        self.assertType(blogpostrevisions, bp1.revisions)
        for rev in bp1.revisions:
            self.assertType(blogpostrevision, rev)

        # ... then load
        
        # TODO: The second save should insert a revision record with a blog
        # value of None
        return
        self.assertEq(None, bp.revisions.second.blog)
        bp1 = blogpost(bp.id)
        self.assertCount(2, bp1.revisions)
        self.assertEq(bp1.blog.id, bp1.revisions.first.blog.id)
        self.assertEq(None, bp1.revisions.second.blog)

    def it_calls_body(self): 
        bp = blogpost()
        bp.blog = self.blog
        self.assertNone(bp.body)
        bp.save()
        self.assertEmptyString(bp.body)

        bp.body = test_article.Smallpostbody
        self.assertEq(test_article.Smallpostbody, bp.body)

        bp.save()
        self.assertEq(test_article.Smallpostbody, bp.body)

        bp = blogpost(bp.id)
        self.assertEq(test_article.Smallpostbody, bp.body)

    def it_calls_created_at(self):
        bp = blogpost()
        bp.blog = self.blog
        self.assertNone(bp.created_at)
        before = datetime.now().replace(microsecond=0)

        bp.blog = self.blog
        bp.save()

        after = datetime.now().replace(microsecond=0)

        self.assertLe(before, bp.created_at)
        self.assertGe(after, bp.created_at)

        created_at = bp.created_at

        bp = blogpost(bp.id)
        self.assertEq(created_at, bp.created_at)

    def it_calls_title(self):
        bp = blogpost()
        bp.blog = self.blog
        self.assertNone(bp.title)

        bp.save()

        self.assertEmptyString(bp.title)

        bp.title = test_article.Smallposttitle
        self.assertEq(test_article.Smallposttitle, bp.title)

        bp.save()
        self.assertEq(test_article.Smallposttitle, bp.title)

        bp = blogpost(bp.id)
        self.assertEq(test_article.Smallposttitle, bp.title)

    def it_calls_slug(self):
        bp = blogpost()
        bp.blog = self.blog
        self.assertNone(bp.slug)

        bp.save()

        self.assertEmptyString(bp.slug)

        slug = str(uuid4())
        bp.slug = slug
        self.assertEq(slug, bp.slug)

        bp.save()
        self.assertEq(slug, bp.slug)

        bp = blogpost(bp.id)
        self.assertEq(slug, bp.slug)

    def it_calls_title_and_slug(self):
        bp = blogpost()
        bp.blog = self.blog
        title = 'Herp derp'
        slug = re.sub(r'\W+', '-', title).strip('-').lower()
        bp.title = title

        self.assertEq(slug, bp.slug)

        bp.save()
        self.assertEq(slug, bp.slug)

        bp = blogpost(bp.id)
        self.assertEq(slug, bp.slug)

    def it_calls_excerpt(self):
        bp = blogpost()
        bp.blog = self.blog
        self.assertNone(bp.excerpt)
        bp.save()
        self.assertEmptyString(bp.excerpt)

        bp = blogpost(bp.id)
        self.assertEmptyString(bp.excerpt)

        bp = blogpost()
        bp.blog = self.blog
        self.assertNone(bp.excerpt)
        bp.save()
        self.assertEmptyString(bp.excerpt)
        bp = blogpost(bp.id)
        self.assertEmptyString(bp.excerpt)

        bp = blogpost()
        bp.blog = self.blog
        bp.excerpt = test_article.Smallpostexcerpt
        self.assertEq(test_article.Smallpostexcerpt, bp.excerpt)
        bp.save()
        self.assertEq(test_article.Smallpostexcerpt, bp.excerpt)
        bp = blogpost(bp.id)
        self.assertEq(test_article.Smallpostexcerpt, bp.excerpt)

    def it_calls_status(self): 
        bp = blogpost()
        bp.blog = self.blog
        self.assertNone(bp.status)
        bp.save()
        self.assertEq(blogpost.Draft, bp.status)
        bp = blogpost(bp.id)
        self.assertEq(blogpost.Draft, bp.status)

        bp = blogpost()
        bp.blog = self.blog
        bp.status = blogpost.Pending
        self.assertEq(blogpost.Pending, bp.status)
        bp.save()
        self.assertEq(blogpost.Pending, bp.status)
        bp = blogpost(bp.id)
        self.assertEq(blogpost.Pending, bp.status)

    def it_calls_iscommentable(self): 
        bp = blogpost()
        bp.blog = self.blog
        self.assertNone(bp.iscommentable)
        bp.save()
        self.assertFalse(bp.iscommentable)
        bp = blogpost(bp.id)
        self.assertFalse(bp.iscommentable)

        bp = blogpost()
        bp.blog = self.blog
        bp.iscommentable = True
        self.assertTrue(bp.iscommentable)
        bp.save()
        self.assertTrue(bp.iscommentable)
        bp = blogpost(bp.id)
        self.assertTrue(bp.iscommentable)

        bp = blogpost()
        bp.blog = self.blog
        bp.iscommentable = False
        self.assertFalse(bp.iscommentable)
        bp.save()
        self.assertFalse(bp.iscommentable)
        bp = blogpost(bp.id)
        self.assertFalse(bp.iscommentable)

    def it_searches_by_id(self):
        bp = blogpost()
        bp.blog = self.blog
        bp.save()
        id = bp.id

        bp = blogpost(id)
        self.assertEq(id,   bp.id)

    def it_searches_by_slug(self):
        bp = blogpost()
        bp.blog = self.blog
        slug = str(uuid4())
        bp.slug = slug
        bp.save()
        id = bp.id

        bp = blogpost(slug)
        self.assertEq(slug, bp.slug)
        self.assertEq(id,   bp.id)

    def it_calls_slug_and_title(self):
        title = test_article.Smallposttitle + str(uuid4())
        slug = re.sub(r'\W+', '-', title).strip('-').lower()

        bp = blogpost()
        bp.blog = self.blog
        bp.title = title
        self.assertEq(slug, bp.slug)
        self.assertEq(title, bp.title)
        bp.save()
        self.assertEq(slug, bp.slug)
        self.assertEq(title, bp.title)
        bp = blogpost(bp.id)
        self.assertEq(slug, bp.slug)
        self.assertEq(title, bp.title)
        bp = blogpost(bp.id)
        self.assertEq(slug, bp.slug)
        self.assertEq(title, bp.title)

        title = test_article.Smallposttitle + str(uuid4())
        slug = re.sub(r'\W+', '-', title).strip('-').lower()
        bp = blogpost()
        bp.blog = self.blog
        self.assertNone(bp.slug)
        self.assertEq(None, bp.title) 
        bp.title = title
        self.assertEq(slug, bp.slug)
        self.assertEq(title, bp.title)

        bp.save()
        self.assertEq(title, bp.title)
        self.assertEq(slug, bp.slug)
        bp = blogpost(bp.id)
        self.assertEq(title, bp.title)
        self.assertEq(slug, bp.slug)

        bp = blogpost()
        bp.blog = self.blog
        self.assertEq(None, bp.title)
        bp.save()
        self.assertEq('', bp.title)
        self.assertEmptyString(bp.slug)
        bp = blogpost(bp.id)
        self.assertEmptyString(bp.slug)
        self.assertEq('', bp.title)

        bp = blogpost()
        bp.blog = self.blog
        bp.slug = 'Herp Derp'
        self.assertEq('Herp Derp', bp.slug)
        self.assertEq(None, bp.title)
        bp.title = title
        self.assertEq('Herp Derp', bp.slug)
        bp.save()
        self.assertEq(title, bp.title)
        self.assertEq('Herp Derp', bp.slug)
        bp = blogpost(bp.id)
        self.assertEq(title, bp.title)
        self.assertEq('Herp Derp', bp.slug)

    def it_saves_x_revisions_with_empty_properties(self):
        bp = blogpost()
        bp.blog = self.blog
        bp.body = test_article.Smallpostbody
        title = test_article.Smallposttitle + ' - ' + str(uuid4())
        bp.title = title
        bp.excerpt = test_article.Smallpostexcerpt 
        bp.status = blogpost.Pending
        bp.iscommentable = True

        bp.save()

        for i in range(2):
            bp.title = ''
            bp.excerpt = ''
            bp.slug = ''
            bp.save()

            bp = blogpost(bp.id)
            bp.blog = self.blog
            self.assertEmptyString(bp.title)
            self.assertEmptyString(bp.excerpt)
            self.assertEq(blogpost.Pending, bp.status)
            self.assertTrue(bp.iscommentable)
            self.assertEmptyString(bp.slug)
            
    def it_has_valid_revisions(self):
        # TODO Ensure that each of the revisions is the revision property are
        # the correct type, etc. Ensure this is true when a blogpost is reloaded.
        # Copy this to test_article as well.
        pass

    def it_saves_x_revisions(self):
        bp = blogpost()
        bp.blog = self.blog
        bp.body = test_article.Smallpostbody
        title = test_article.Smallposttitle + ' - ' + str(uuid4())
        bp.title = title
        bp.excerpt = test_article.Smallpostexcerpt 
        bp.status = blogpost.Pending
        bp.iscommentable = True

        bp.save()

        created_at = bp.created_at
        
        self.assertNotNone(bp.id)
        self.assertEq(test_article.Smallpostbody, bp.body)
        self.assertEq(title, bp.title)
        self.assertEq(test_article.Smallpostexcerpt, bp.excerpt)
        self.assertEq(blogpost.Pending, bp.status)
        self.assertEq(True, bp.iscommentable)
        slug = re.sub(r'\W+', '-', bp.title).strip('-').lower()
        self.assertEq(slug, bp.slug)

        x = 20

        for i in range(x):
            id = bp.id

            # Mutate the body to ensure revision patching works
            if i < 5:
                newbody = bp.body + 'X'
            elif i >= 5 and i <= 10:
                newbody = ''
                for j, c in enumerate(bp.body):
                    if j == i:
                        c = 'x'
                    newbody += c
            elif i > 10:
                bp.slug = 'walden-or-life-in-the-woods-hard-set'
                newbody = 'X' + bp.body
                
            bp.body = newbody

            bp.title = newtitle = test_article.Smallposttitle + ' Rev ' + str(i)
            bp.excerpt = newexcerpt = test_article.Smallpostexcerpt + ' Rev ' + str(i)
            bp.status = blogpost.Publish
            bp.iscommentable = i % 2 == 0
            
            bp.save()

            self.assertNotNone(bp.id)
            self.assertEq(id, bp.id)
            self.assertEq(newbody, bp.body)
            self.assertEq(created_at, bp.created_at)
            self.assertEq(newtitle, bp.title)
            self.assertEq(newexcerpt, bp.excerpt)
            self.assertEq(blogpost.Publish, bp.status)
            self.assertEq(i % 2 == 0, bp.iscommentable)
            if i > 10:
                self.assertEq('walden-or-life-in-the-woods-hard-set', bp.slug)
            else:
                self.assertEq(slug, bp.slug)

    def _createblogpost(self):
        bp = blogpost()
        bp.blog = self.blog
        bp.body = test_article.Smallpostbody
        bp.title = test_article.Smallposttitle 
        bp.excerpt = test_article.Smallpostexcerpt 
        bp.status = blogpost.Pending
        bp.iscommentable = True

        bp.save()

        x = 20

        for i in range(x):
            id = bp.id

            # Mutate the body to ensure revision patching works
            if i < 5:
                newbody = bp.body + 'X'
            elif i >= 5 and i <= 10:
                newbody = ''
                for j, c in enumerate(bp.body):
                    if j == i:
                        c = 'x'
                    newbody += c
            elif i > 10:
                newbody = 'X' + bp.body
                
            bp.body = newbody

            bp.title = newtitle = test_article.Smallposttitle + ' Rev ' + str(i)
            bp.excerpt = newexcerpt = test_article.Smallpostexcerpt + ' Rev ' + str(i)
            bp.status = blogpost.Publish
            bp.iscommentable = i % 2 == 0
            
            bp.save()
        return bp

    def it_retrives_blogpost(self):
        bp1 = self._createblogpost()
        bp2 = blogpost(bp1.id)

        self.assertTrue(type(bp2.id) == uuid.UUID)
        self.assertEq(bp1.id,                bp2.id)

        self.assertEq(type(bp2.created_at),  datetime)
        self.assertEq(bp1.created_at,        bp2.created_at)

        self.assertEq(bp1.body,              bp2.body)
        self.assertEq(bp1.title,             bp2.title)
        self.assertEq(bp1.excerpt,           bp2.excerpt)
        self.assertEq(bp1.status,            bp2.status)
        self.assertEq(bp1.iscommentable,     bp2.iscommentable)


    
class test_article(tester):
    
    Smallposttitle = 'Walden; or, Life in the Woods'

    Smallpostbody = """When I wrote the following pages, or rather the bulk of them,
I lived alone, in the woods, a mile from any neighbor, in a house which I
had built myself, on the shore of Walden Pond, in Concord, Massachusetts,
and earned my living by the labor of my hands only. I lived there two years
and two months. At present I am a sojourner in civilized life again."""

    Smallpostexcerpt = """Walden is a book by noted transcendentalist Henry
David Thoreau. The text is a reflection upon simple living in natural
surroundings. The work is part personal declaration of independence, social
experiment, voyage of spiritual discovery, satire, and-to some degree-a
manual for self-reliance."""

    def __init__(self):
        super().__init__()
        articlerevisions().RECREATE()

    def it_loads_as_valid(self):
        art = article()
        art.body = test_article.Smallpostbody
        title = test_article.Smallposttitle + ' - ' + str(uuid4())
        art.title  = title
        slug = re.sub(r'\W+', '-', art.title).strip('-').lower()
        art.excerpt = test_article.Smallpostexcerpt 
        art.status = article.Pending
        art.iscommentable = True
        art.save()
        art = article(art.id)
        self.assertValid(art)

    def it_saves_x_revisions_with_null_properties(self):
        art = article()
        art.body = test_article.Smallpostbody
        title = test_article.Smallposttitle + ' - ' + str(uuid4())
        art.title  = title
        slug = re.sub(r'\W+', '-', art.title).strip('-').lower()
        art.excerpt = test_article.Smallpostexcerpt 
        art.status = article.Pending
        art.iscommentable = True

        art.save()

        x = 4
        for i in range(x):
            if i < x / 2:
                art.title = None
                art.excerpt = None
                art.slug = None
            else:
                art.body = test_article.Smallpostbody  + ' Rev: ' + str(i)
                revisedtitle = title + ' Rev: ' + str(i)
                art.title = revisedtitle
                art.excerpt = test_article.Smallpostexcerpt  + ' Rev: ' + str(i)
                
            art.save()

            art = article(art.id)

            if i < x / 2:
                self.assertEq(test_article.Smallpostbody, art.body)
                self.assertEq(title, art.title)
                self.assertEq(test_article.Smallpostexcerpt, art.excerpt)
            else:
                self.assertEq(test_article.Smallpostbody + ' Rev: ' + str(i), art.body)
                self.assertEq(revisedtitle, art.title)
                self.assertEq(test_article.Smallpostexcerpt + ' Rev: ' + str(i), art.excerpt)
            self.assertEq(article.Pending, art.status)
            self.assertTrue(art.iscommentable)
            self.assertEq(slug, art.slug)

    def it_calls_body(self): 
        art = article()
        self.assertNone(art.body)
        art.save()
        self.assertEmptyString(art.body)

        art.body = test_article.Smallpostbody
        self.assertEq(test_article.Smallpostbody, art.body)

        art.save()
        self.assertEq(test_article.Smallpostbody, art.body)

        art = article(art.id)
        self.assertEq(test_article.Smallpostbody, art.body)

    def it_calls_created_at(self):
        art = article()
        self.assertNone(art.created_at)
        before = datetime.now().replace(microsecond=0)

        art.save()

        after = datetime.now().replace(microsecond=0)

        self.assertLe(before, art.created_at)
        self.assertGe(after, art.created_at)

        created_at = art.created_at

        art = article(art.id)
        self.assertEq(created_at, art.created_at)

    def it_calls_title(self):
        art = article()
        self.assertNone(art.title)

        art.save()

        self.assertEmptyString(art.title)

        art.title = test_article.Smallposttitle
        self.assertEq(test_article.Smallposttitle, art.title)

        art.save()
        self.assertEq(test_article.Smallposttitle, art.title)

        art = article(art.id)
        self.assertEq(test_article.Smallposttitle, art.title)

    def it_calls_slug(self):
        art = article()
        self.assertNone(art.slug)

        art.save()

        self.assertEmptyString(art.slug)

        slug = str(uuid4())
        art.slug = slug
        self.assertEq(slug, art.slug)

        art.save()
        self.assertEq(slug, art.slug)

        art = article(art.id)
        self.assertEq(slug, art.slug)

    def it_calls_title_and_slug(self):
        art = article()
        title = 'Herp derp'
        slug = re.sub(r'\W+', '-', title).strip('-').lower()
        art.title = title

        self.assertEq(slug, art.slug)

        art.save()
        self.assertEq(slug, art.slug)

        art = article(art.id)
        self.assertEq(slug, art.slug)

    def it_calls_excerpt(self):
        art = article()
        self.assertNone(art.excerpt)
        art.save()
        self.assertEmptyString(art.excerpt)

        art = article(art.id)
        self.assertEmptyString(art.excerpt)

        art = article()
        self.assertNone(art.excerpt)
        art.save()
        self.assertEmptyString(art.excerpt)
        art = article(art.id)
        self.assertEmptyString(art.excerpt)

        art = article()
        art.excerpt = test_article.Smallpostexcerpt
        self.assertEq(test_article.Smallpostexcerpt, art.excerpt)
        art.save()
        self.assertEq(test_article.Smallpostexcerpt, art.excerpt)
        art = article(art.id)
        self.assertEq(test_article.Smallpostexcerpt, art.excerpt)

    def it_calls_status(self): 
        art = article()
        self.assertNone(art.status)
        art.save()
        self.assertEq(article.Draft, art.status)
        art = article(art.id)
        self.assertEq(article.Draft, art.status)

        art = article()
        art.status = article.Pending
        self.assertEq(article.Pending, art.status)
        art.save()
        self.assertEq(article.Pending, art.status)
        art = article(art.id)
        self.assertEq(article.Pending, art.status)

    def it_calls_iscommentable(self): 
        art = article()
        self.assertNone(art.iscommentable)
        art.save()
        self.assertFalse(art.iscommentable)
        art = article(art.id)
        self.assertFalse(art.iscommentable)

        art = article()
        art.iscommentable = True
        self.assertTrue(art.iscommentable)
        art.save()
        self.assertTrue(art.iscommentable)
        art = article(art.id)
        self.assertTrue(art.iscommentable)

        art = article()
        art.iscommentable = False
        self.assertFalse(art.iscommentable)
        art.save()
        self.assertFalse(art.iscommentable)
        art = article(art.id)
        self.assertFalse(art.iscommentable)

    def it_searches_by_id(self):
        art = article()
        art.save()
        id = art.id

        art = article(id)
        self.assertEq(id,   art.id)

    def it_searches_by_slug(self):
        art = article()
        slug = str(uuid4())
        art.slug = slug
        art.save()
        id = art.id

        art = article(slug)
        self.assertEq(slug, art.slug)
        self.assertEq(id,   art.id)

    def it_calls_wont_save_if_there_are_brokenrules(self): 
        # TODO
        return
        art = article()
        try:
            art.save()
        except brokenruleserror as ex:
            self.assertIs(art, ex.object)
        except:
            msg = ('BrokenRulesError expected however a different exception '
                  ' was thrown: ' + str(type(ex)))
            self.assertFail(msg)
        else:
            self.assertFail('No exception thrown on save of invalid object.')

    def it_calls_slug_and_title(self):
        title = test_article.Smallposttitle + str(uuid4())
        slug = re.sub(r'\W+', '-', title).strip('-').lower()

        art = article()
        art.title = title
        self.assertEq(slug, art.slug)
        self.assertEq(title, art.title)
        art.save()
        self.assertEq(slug, art.slug)
        self.assertEq(title, art.title)
        art = article(art.id)
        self.assertEq(slug, art.slug)
        self.assertEq(title, art.title)
        art = article(art.id)
        self.assertEq(slug, art.slug)
        self.assertEq(title, art.title)

        title = test_article.Smallposttitle + str(uuid4())
        slug = re.sub(r'\W+', '-', title).strip('-').lower()
        art = article()
        self.assertNone(art.slug)
        self.assertEq(None, art.title) 
        art.title = title
        self.assertEq(slug, art.slug)
        self.assertEq(title, art.title)

        art.save()
        self.assertEq(title, art.title)
        self.assertEq(slug, art.slug)
        art = article(art.id)
        self.assertEq(title, art.title)
        self.assertEq(slug, art.slug)

        art = article()
        self.assertEq(None, art.title)
        art.save()
        self.assertEq('', art.title)
        self.assertEmptyString(art.slug)
        art = article(art.id)
        self.assertEmptyString(art.slug)
        self.assertEq('', art.title)

        art = article()
        art.slug = 'Herp Derp'
        self.assertEq('Herp Derp', art.slug)
        self.assertEq(None, art.title)
        art.title = title
        self.assertEq('Herp Derp', art.slug)
        art.save()
        self.assertEq(title, art.title)
        self.assertEq('Herp Derp', art.slug)
        art = article(art.id)
        self.assertEq(title, art.title)
        self.assertEq('Herp Derp', art.slug)

    def it_saves_x_revisions_with_empty_properties(self):
        art = article()
        art.body = test_article.Smallpostbody
        title = test_article.Smallposttitle + ' - ' + str(uuid4())
        art.title = title
        art.excerpt = test_article.Smallpostexcerpt 
        art.status = article.Pending
        art.iscommentable = True

        art.save()

        for i in range(2):
            art.title = ''
            art.excerpt = ''
            art.slug = ''
            art.save()

            art = article(art.id)
            self.assertEmptyString(art.title)
            self.assertEmptyString(art.excerpt)
            self.assertEq(article.Pending, art.status)
            self.assertTrue(art.iscommentable)
            self.assertEmptyString(art.slug)

    def it_saves_x_revisions(self):
        art = article()
        art.body = test_article.Smallpostbody
        title = test_article.Smallposttitle + ' - ' + str(uuid4())
        art.title = title
        art.excerpt = test_article.Smallpostexcerpt 
        art.status = article.Pending
        art.iscommentable = True

        art.save()

        created_at = art.created_at
        
        self.assertNotNone(art.id)
        self.assertEq(test_article.Smallpostbody, art.body)
        self.assertEq(title, art.title)
        self.assertEq(test_article.Smallpostexcerpt, art.excerpt)
        self.assertEq(article.Pending, art.status)
        self.assertEq(True, art.iscommentable)
        slug = re.sub(r'\W+', '-', art.title).strip('-').lower()
        self.assertEq(slug, art.slug)

        x = 20

        for i in range(x):
            id = art.id

            # Mutate the body to ensure revision patching works
            if i < 5:
                newbody = art.body + 'X'
            elif i >= 5 and i <= 10:
                newbody = ''
                for j, c in enumerate(art.body):
                    if j == i:
                        c = 'x'
                    newbody += c
            elif i > 10:
                art.slug = 'walden-or-life-in-the-woods-hard-set'
                newbody = 'X' + art.body
                
            art.body = newbody

            art.title = newtitle = test_article.Smallposttitle + ' Rev ' + str(i)
            art.excerpt = newexcerpt = test_article.Smallpostexcerpt + ' Rev ' + str(i)
            art.status = article.Publish
            art.iscommentable = i % 2 == 0
            
            art.save()

            self.assertNotNone(art.id)
            self.assertEq(id, art.id)
            self.assertEq(newbody, art.body)
            self.assertEq(created_at, art.created_at)
            self.assertEq(newtitle, art.title)
            self.assertEq(newexcerpt, art.excerpt)
            self.assertEq(article.Publish, art.status)
            self.assertEq(i % 2 == 0, art.iscommentable)
            if i > 10:
                self.assertEq('walden-or-life-in-the-woods-hard-set', art.slug)
            else:
                self.assertEq(slug, art.slug)

    def _createblogpost(self):
        art = article()
        art.body = test_article.Smallpostbody
        art.title = test_article.Smallposttitle 
        art.excerpt = test_article.Smallpostexcerpt 
        art.status = article.Pending
        art.iscommentable = True

        art.save()

        x = 20

        for i in range(x):
            id = art.id

            # Mutate the body to ensure revision patching works
            if i < 5:
                newbody = art.body + 'X'
            elif i >= 5 and i <= 10:
                newbody = ''
                for j, c in enumerate(art.body):
                    if j == i:
                        c = 'x'
                    newbody += c
            elif i > 10:
                newbody = 'X' + art.body
                
            art.body = newbody

            art.title = newtitle = test_article.Smallposttitle + ' Rev ' + str(i)
            art.excerpt = newexcerpt = test_article.Smallpostexcerpt + ' Rev ' + str(i)
            art.status = article.Publish
            art.iscommentable = i % 2 == 0
            
            art.save()
        return art

    def it_retrives_blogpost(self):
        bp1 = self._createblogpost()
        bp2 = article(bp1.id)

        self.assertTrue(type(bp2.id) == uuid.UUID)
        self.assertEq(bp1.id,                bp2.id)

        self.assertEq(type(bp2.created_at),  datetime)
        self.assertEq(bp1.created_at,        bp2.created_at)

        self.assertEq(bp1.body,              bp2.body)
        self.assertEq(bp1.title,             bp2.title)
        self.assertEq(bp1.excerpt,           bp2.excerpt)
        self.assertEq(bp1.status,            bp2.status)
        self.assertEq(bp1.iscommentable,     bp2.iscommentable)

class test_articlesrevisions(tester):
    def __init__(self):
        super().__init__()
        articlerevisions().RECREATE()

class test_articlesrevision(tester):
    def __init__(self):
        super().__init__()
        articlerevisions().RECREATE()

    def it_instantiates(self):
        rev = articlerevision()
        self.assertNone(rev.id)
        self.assertNone(rev.authors)
        self.assertNone(rev.created_at)
        self.assertNone(rev.title)
        self.assertNone(rev.body)
        self.assertNone(rev.excerpt)
        self.assertEq(article.Draft, rev.status)
        self.assertFalse(rev.iscommentable)
        self.assertNone(rev.slug)

    def it_fails_on_save_when_invalid(self):
        rev = articlerevision()
        try:
            rev.save()
        except brokenruleserror as ex:
            self.assertIs(rev, ex.object)
        except Exception as ex:
            msg = ('brokenruleserror expected however a different exception '
                  ' was thrown: ' + str(type(ex)))
            self.assertFail(msg)
        else:
            self.assertFail('No exception thrown on save of invalid object.')

    def it_fails_to_load_given_nonexistent_id(self):
        try:
            rev = articlerevision(uuid4())
        except Exception as ex:
            self.assertTrue(True)
        else:
            self.assertFail('Exception was not thrown')

    def it_loads_as_valid(self):
        rev = articlerevision()
        rev.body = test_article.Smallpostbody
        rev.title = test_article.Smallposttitle + str(uuid4())
        rev.save()

        rev = articlerevision(rev.id)
        self.assertValid(rev)

    def it_breaks_diff_rules(self):
        # Diff must be empty for root revisions
        rev = articlerevision()
        rev.body = test_article.Smallpostbody
        rev.title = test_article.Smallposttitle
        rev.diff = diff.diff('herp', 'derp')
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('diff', 'empty'))

        # Fix
        rev.diff = None
        self.assertValid(rev)

        # Break the rule that says a diff must be of type diff.diff
        rent = articlerevision()
        rent.body = test_article.Smallpostbody
        rent.title = test_article.Smallposttitle
        rent.diff = diff.diff('herp', 'derp')

        rev._parent = rent
        rev.body = None
        rev.diff = 'wrong type'
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('diff', 'valid'))

    def it_breaks_title_rules(self):
        # Root revisions must have non null titles
        rev = articlerevision()
        rev.body = test_article.Smallpostbody
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('title', 'full'))

        # Non-root revisions can have null titles
        rev._parent = articlerevision()
        self.assertCount(0, rev.brokenrules)

        # Root revisions can have empty strings as titles
        rev = articlerevision()
        rev.body = test_article.Smallpostbody
        rev.title = ''
        self.assertCount(0, rev.brokenrules)

        # Revisions titles must be strings
        rev.title = 123
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('title', 'valid'))
        rev._parent = articlerevision() # Make non-root
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('title', 'valid'))

        # Title must be less than 500 characters
        rev = articlerevision()
        rev.body = test_article.Smallpostbody
        rev.title = 'X' * 500
        self.assertCount(0, rev.brokenrules)
        rev.title = 'X' * 501
        self.assertCount(1, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('title', 'fits'))

    def it_breaks_status_rules(self):
        rev = articlerevision()
        rev.body = test_article.Smallpostbody
        rev.title = test_article.Smallposttitle
        for st in article.Statuses:
            rev.status = st
            self.assertCount(0, rev.brokenrules)

        for st in ('wrong-type', 9999, object()):
            rev.status = st
            self.assertCount(1, rev.brokenrules)
            self.assertTrue(rev.brokenrules.contains('status', 'valid'))

    def it_breaks_body_rules(self):
        # Body must be full for root revisions
        rev = articlerevision()
        self.assertCount(2, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('body', 'full'))
        self.assertTrue(rev.brokenrules.contains('title', 'full'))

        # Create a parent then test the child
        rent = articlerevision()
        rent.body = test_article.Smallpostbody
        rent.title = test_article.Smallposttitle
        rent.diff = diff.diff('herp', 'derp')

        # A body and a diff shouldn't exist in the same record
        rev._parent = rent
        rev.diff = diff.diff('herp', 'derp')
        rev.body = test_article.Smallpostbody
        self.assertCount(2, rev.brokenrules)
        self.assertTrue(rev.brokenrules.contains('diff', 'valid'))

        # A non-root revision should can have a body but no diff. This
        # may be useful for caching or other isssues such as a failure to
        # create a diff.
        rev.body = test_article.Smallpostbody
        rev.diff = None
        self.assertValid(rev)

    def it_retrieves(self):
        rev = articlerevision()
        rev.body = test_article.Smallpostbody
        rev.title = test_article.Smallposttitle + str(uuid4())
        rev.save()

        rev = articlerevision(rev.id)
        self.assertEq(rev.id, rev.id)

class test_persons(tester):
    def __init__(self):
        super().__init__()
        persons().RECREATE()

    def it_calls__str__(self):
        ps = persons()

        p = person()
        p.firstname   =  'Ellan'
        p.lastname    =  'Page'
        p.email       =  'epage@fakemail.com'
        p.phone       =  '555 555 5555'
        ps += p

        p = person()
        p.firstname   =  'Jessica'
        p.lastname    =  'Chastain'
        p.email       =  'jchastain@fakemail.com'
        p.phone       =  '555 555 5555'
        ps += p

        p = person()
        p.firstname   =  'James'
        p.lastname    =  'Cromwell'
        p.email       =  'jcromwell@fakemail.com'
        p.phone       =  '555 555 5555'
        ps += p

        ps.save()
        ps = persons().ALL()
        print(ps)

        expect = """+--------------------------------------------------------------------------------+
| id | firstname | middlename | lastname | email                  | phone        |
|-------------------------------------------------------------------------------|
|    | Ellan     |            | Page     | epage@fakemail.com     | 555 555 5555 |
|--------------------------------------------------------------------------------|
|    | Jessica   |            | Chastain | jchastain@fakemail.com | 555 555 5555 |
|--------------------------------------------------------------------------------|
|    | James     |            | Cromwell | jcromwell@fakemail.com | 555 555 5555 |
+--------------------------------------------------------------------------------+
"""

        self.assertEq(expect, str(ps))

    def it_searches(self):
        ps = persons()
        p = person()
        p.firstname   =  'Ellan'
        p.lastname    =  'Page'
        p.email       =  'epage@fakemail.com'
        p.phone       =  '555 555 1111'
        ps += p

        p = person()
        p.firstname   =  'Jessica'
        p.lastname    =  'Chastain'
        p.email       =  'jchastain@fakemail.com'
        p.phone       =  '555 555 2222'
        ps += p

        p = person()
        p.firstname   =  'James'
        p.lastname    =  'Cromwell'
        p.email       =  'jcromwell@fakemail.com'
        p.phone       =  '555 555 3333'
        ps += p

        ps.save()

        for s in 'james', 'Cromwell', 'jcromwell', 3333:
            ps = persons.search(s)

            self.assertOne(ps)
            self.assertEq('James',     ps.first.firstname)
            self.assertEq('Cromwell',  ps.first.lastname)

        ps = persons.search(555)
        self.assertThree(ps)
    
class test_person(tester):
    def __init__(self):
        super().__init__()
        persons().RECREATE()

    def it_calls__str__(self):
        p = person()
        p.firstname   =  'Tom'
        p.lastname    =  'Regan'
        p.email       =  'tregan@fakemail.com'
        p.phone       =  '555 555 5555'

        expect = """First name: Tom
Last name: Regan
Email: tregan@fakemail.com
Phone: 555 555 5555
"""
        self.assertEq(expect, str(p)) 

    def it_calls_save(self):
        p = person()
        p.firstname   =  'Gary'
        p.middlename  =  'Lawrence'
        p.lastname    =  'Francione'
        p.email       =  'glawrence@fakemail.com'
        p.phone       =  '480 555 5555'
        p.save()

    def it_loads(self):
        p = person()
        p.firstname = 'Gary'
        p.middlename = 'Lawrence'
        p.lastname = 'Francione'
        p.email = 'glawrence@fakemail.com'
        p.phone = '555 555 5555'
        p.save()

        p1 = person(p.id)

        for prop in ('firstname', 'middlename', 'lastname', 'id', 'email', 'phone'):
            self.assertEq(getattr(p, prop), getattr(p1, prop))

    def it_deletes(self):
        p = person()
        p.firstname   =  'Peter'
        p.middlename  =  'Albert David'
        p.lastname    =  'Singer'
        p.email       =  'psinger@fakemail.com'
        p.phone       =  '555 555 5555'

        p.save()
        p = person(p.id)
        cnt = p.delete()

        self.assertEq(1, cnt)
        self.assertTrue(p.isnew)

        cnt = p.delete()
        self.assertEq(0, cnt)

        try:
            p = person(p.id)
        except Exception:
            pass
        else:
            self.assertFail('No exception thrown')

    def it_calls_fullname(self):
        p = person()
        p.firstname = 'Gary'
        p.middlename = 'Lawrence'
        p.lastname = 'Francione'
        p.email = 'glawrence@fakemail.com'
        p.phone = '555 555 5555'

        self.assertEq(p.firstname + ' ' + p.lastname, p.fullname)

    def it_calls_name(self):
        p = person()
        p.firstname = 'Gary'
        p.middlename = 'Lawrence'
        p.lastname = 'Francione'
        p.email = 'glawrence@fakemail.com'
        p.phone = '555 555 5555'

        self.assertEq(p.fullname, p.name)

    def it_breaks_firstname_rule(self):
        p = person()
        p.firstname = 'X' * 255
        p.middlename = 'Lawrence'
        p.lastname = 'Francione'
        p.email = 'glawrence@fakemail.com'
        p.phone = '555 555 5555'

        self.assertZero(p.brokenrules)

        p.firstname = 'X' * 256
        self.assertCount(1, p.brokenrules)
        self.assertTrue(p.brokenrules.contains('firstname', 'fits'))

    def it_breaks_middlename_rule(self):
        p = person()
        p.firstname = 'Gary'
        p.middlename = 'X' * 255
        p.lastname = 'Francione'
        p.email = 'glawrence@fakemail.com'
        p.phone = '555 555 5555'

        self.assertZero(p.brokenrules)

        p.middlename = 'X' * 256
        self.assertCount(1, p.brokenrules)
        self.assertTrue(p.brokenrules.contains('middlename', 'fits'))

    def it_breaks_lastname_rule(self):
        p = person()
        p.firstname = 'Gary'
        p.middlename = 'Lawrence'
        p.lastname = ''
        p.email = 'glawrence@fakemail.com'
        p.phone = '555 555 5555'

        self.assertCount(1, p.brokenrules)
        self.assertTrue(p.brokenrules.contains('lastname', 'full'))

        p.lastname = 'X' * 255
        self.assertZero(p.brokenrules)

        p.lastname = 'X' * 256
        self.assertCount(1, p.brokenrules)
        self.assertTrue(p.brokenrules.contains('lastname', 'fits'))

    def it_breaks_email_rule(self):
        p = person()
        p.firstname = 'Gary'
        p.middlename = 'Lawrence'
        p.lastname = 'Francione'
        p.email = 'not-an-email-address'
        p.phone = '555 555 5555'

        self.assertCount(1, p.brokenrules)
        self.assertTrue(p.brokenrules.contains('email', 'valid'))

        p.email = ('X' * 246) + '@mail.com'
        self.assertZero(p.brokenrules)

        p.email = ('X' * 247) + '@mail.com'
        self.assertCount(1, p.brokenrules)
        self.assertTrue(p.brokenrules.contains('email', 'fits'))

    def it_breaks_phone_rule(self):
        p = person()
        p.firstname = 'Gary'
        p.middlename = 'Lawrence'
        p.lastname = 'Francione'
        p.email = 'glawrence@fakemail.com'
        p.phone = 'X' * 255

        self.assertZero(p.brokenrules)

        p.phone = 'X' * 256
        self.assertCount(1, p.brokenrules)
        self.assertTrue(p.brokenrules.contains('phone', 'fits'))

    def it_wont_save_invaild(self):
        p = person()
        p.firstname = 'Gary'
        p.middlename = 'Lawrence'
        p.email = 'glawrence@fakemail.com'
        p.phone = '555 555 5555'
        p.lastname = ''

        try:
            p.save()
        except brokenruleserror:
            pass # This should happen
        except Exception as ex:
            self.assertFail('Incorrect exception type: ' + str(type(ex)))
        else:
            self.assertFail("Invalid person object didn't throw error on save")

    def it_updates(self):
        p = person()
        p.firstname = 'Gary'
        p.middlename = 'Lawrence'
        p.lastname = 'Francione'
        p.email = 'glawrence@fakemail.com'
        p.phone = '555 555 5555'
        p.save() # insert

        p = person(p.id)
        p.firstname = 'Gary - update'
        p.middlename = 'Lawrence - update'
        p.lastname = 'Francione - update'
        p.email = 'glawrence@fakemail.com'
        p.phone = '555 555 5555'
        p.save() # update

        p1 = person(p.id)
        for prop in ('firstname', 'middlename', 'lastname', 'id', 'email', 'phone'):
            self.assertEq(getattr(p, prop), getattr(p1, prop))

    def it_adds_users(self):
        # Create new person
        p = person()
        p.firstname  =  'Joseph'
        p.lastname   =  'Armstrong'
        p.email      =  'jarmstrong@fakemail.com'
        p.phone      =  '555 555 5555'

        # Create new user
        u = user()
        u.service   =  str(uuid4())
        u.name      =  str(uuid4())
        u.password  =  str(uuid4())

        us = users()
        us += u

        # Add user to person and save
        p.users += u

        # Test p.users
        self.assertEq(u.service,    p.users.first.service)
        self.assertEq(u.name,       p.users.first.name)

        p.save()

        # Reload person; test p.users
        p = person(p.id)

        self.assertEq(u.service,    p.users.first.service)
        self.assertEq(u.name,       p.users.first.name)
        self.assertEq(u.person.id,  p.id)

        # Change property of user, test, save person, reload, test
        name = str(uuid4())
        p.users.first.name = name

        self.assertOne(p.users)
        self.assertTrue(p.isdirty)
        self.assertEq(u.service,    p.users.first.service)
        self.assertEq(name,         p.users.first.name)
        self.assertEq(u.person.id,  p.id)

        return
        p.save()

        p = person(p.id)

        self.assertOne(p.users)
        self.assertEq(u.service,    p.users.first.service)
        self.assertEq(name,         p.users.first.name)
        self.assertEq(u.person.id,  p.id)

        # Create new user, add user, test, save person, test
        u = user()
        u.service   =  str(uuid4())
        u.name      =  str(uuid4())
        u.password  =  str(uuid4())

        us += u

        p.users += u

        self.assertTwo(p.users)
        for u, pu in zip(us, p.users):
            self.assertEq(u.service,    pu.service)
            self.assertEq(u.name,       pu.name)

        p.save()

        p = person(p.id)

        self.assertTwo(p.users)
        for u, pu in zip(us, p.users):
            self.assertEq(u.service,    pu.service)
            self.assertEq(u.name,       pu.name)
            self.assertEq(u.person.id,  p.id)

class test_user(tester):
    def __init__(self):
        super().__init__()
        users().RECREATE()
        roles().RECREATE()
        roles_mm_objects().RECREATE()

        rs = roles()
        for name in (
                        'carapacian-blog-editor', 
                        'carapacian-techblog-editor', 
                        'vegout-blog-editor',
                    ):
            rs += role()
            rs.last.name = name

        rs.save()

    def it_calls_save(self):
        u = user()
        u.service = str(uuid4())
        u.name = 'glawrence'
        u.password = 'secret'
        u.save()

    def it_calls_delete(self):
        u = user()
        u.service   =  str(uuid4())
        u.name      =  str(uuid4())
        u.password  =  str(uuid4())
        u.save()

        u = user(u.id)

        cnt = u.delete()
        self.assertEq(1, cnt)

        cnt = u.delete()
        self.assertEq(0, cnt)

        try:
            u = user(u.id)
        except Exception:
            pass
        else:
            self.assertFail('No exception thrown')

    def it_loads(self):
        u = user()
        u.service = str(uuid4())
        u.name = 'glawrence'
        u.password = 'secret'
        u.save()

        u1 = user(u.id)

        for prop in ('service', 'name', 'hash', 'salt'):
            self.assertEq(getattr(u, prop), getattr(u1, prop))

        self.assertNone(u1.password)

    def it_breaks_service_rule(self):
        u = user()
        u.service = str(uuid4())
        u.name = 'glawrence'
        u.password = 'secret'
        self.assertZero(u.brokenrules)

        for v in (None, '', ' ' * 100):
            u.service = v
            self.assertCount(1, u.brokenrules)
            self.assertTrue(u.brokenrules.contains('service', 'full'))

        u.service = 'X' * 255
        self.assertZero(u.brokenrules)

        u.service = 'X' * 256
        self.assertCount(1, u.brokenrules)
        self.assertTrue(u.brokenrules.contains('service', 'fits'))

    def it_breaks_name_rule(self):
        u = user()
        u.service = str(uuid4())
        u.name = 'glawrence'
        u.password = 'secret'
        self.assertZero(u.brokenrules)

        for v in (None, '', ' ' * 100):
            u.name = v
            self.assertCount(1, u.brokenrules)
            self.assertTrue(u.brokenrules.contains('name', 'full'))

        u.name = 'X' * 255
        self.assertZero(u.brokenrules)

        u.name = 'X' * 256
        self.assertCount(1, u.brokenrules)
        self.assertTrue(u.brokenrules.contains('name', 'fits'))

    def it_breaks_name_and_service_uniqueness_rule(self):
        u = user()
        u.service = str(uuid4())
        u.name = str(uuid4())
        u.password = str(uuid4())
        u.save()

        u1 = user()
        u1.service = u.service
        u1.name = u.name
        u1.password = str(uuid4())
        self.assertTrue(u1.brokenrules.contains('name', 'unique'))

        # Fix
        u1.service = str(uuid4())
        self.assertZero(u1.brokenrules)

        # Break again
        u1.service = u.service
        self.assertTrue(u1.brokenrules.contains('name', 'unique'))

        # Fix another way
        u1.name = str(uuid4())
        self.assertZero(u1.brokenrules)

    def it_validates_password(self):
        pwd = str(uuid4())

        u = user()
        u.service = str(uuid4())
        u.name = 'glawrence'
        u.password = pwd

        self.assertTrue(u.ispassword(pwd))
        self.assertFalse(u.ispassword(str(uuid4())))

        u.save()

        self.assertTrue(u.ispassword(pwd))
        self.assertFalse(u.ispassword(str(uuid4())))

    def it_call_load(self):
        u = user()
        u.service = str(uuid4())
        u.name = str(uuid4())
        u.password = str(uuid4())
        u.save()

        u1 = user.load(u.name, u.service)
        for prop in ('service', 'name', 'hash', 'salt'):
            self.assertEq(getattr(u, prop), getattr(u1, prop))

        u = user.load(str(uuid4()), str(uuid4()))
        self.assertNone(u)

    def it_calls_name(self):
        u = user()
        name = str(uuid4())
        u.name = name
        u.service = str(uuid4())
        u.password = str(uuid4())
        self.assertEq(name, u.name)
        u.save()

        u = user(u.id)
        self.assertEq(name, u.name)

        # Change name
        name = str(uuid4())
        u.name = name

        u.save()

        u = user(u.id)
        self.assertEq(name, u.name)

    def it_calls_service(self):
        u = user()
        name = str(uuid4())
        u.name = name
        service = str(uuid4())
        u.service = service
        u.password = str(uuid4())
        self.assertEq(name, u.name)
        u.save()

        u = user(u.id)
        self.assertEq(service, u.service)

        # Change service
        service = str(uuid4())
        u.service = service

        u.save()

        u = user(u.id)
        self.assertEq(service, u.service)

    def it_calls_password(self):
        u = user()
        name = str(uuid4())
        u.name = name
        service = str(uuid4())
        u.service = service
        pwd = 'password'
        u.password = pwd
        self.assertEq(name, u.name)
        u.save()

        u = user(u.id)
        self.assertTrue(u.ispassword(pwd))

        # Change password
        pwd = 'password0'
        u.password = pwd

        u.save()

        u = user(u.id)
        self.assertTrue(u.ispassword(pwd))

    def it_calls_person(self):
        # Create a person
        p = person()
        p.firstname   =  'Gary'
        p.middlename  =  'Lawrence'
        p.lastname    =  'Francione'
        p.email       =  'gfrancione@mail.com'
        p.phone       =  '5' *  10

        # Create a new user
        u = user()
        u.name      =  str(uuid4())
        u.service   =  str(uuid4())
        u.password  =  str(uuid4())

        # Associate the user with the person
        u.person = p

        # Save user, reload and test association
        u.save()
        u = user(u.id)
        self.assertEq(p.id,          u.person.id)
        self.assertEq(p.firstname,   u.person.firstname)
        self.assertEq(p.middlename,  u.person.middlename)
        self.assertEq(p.lastname,    u.person.lastname)
        self.assertEq(p.email,       u.person.email)
        self.assertEq(p.phone,       u.person.phone)

        # Alter person, save user, reload, test
        phone = '6' * 10
        u.person.phone = phone
        u.save()
        u = user(u.id)
        self.assertEq(p.id,          u.person.id)
        self.assertEq(p.firstname,   u.person.firstname)
        self.assertEq(p.middlename,  u.person.middlename)
        self.assertEq(p.lastname,    u.person.lastname)
        self.assertEq(p.email,       u.person.email)
        self.assertEq(phone,         u.person.phone)

        # Create a second person
        p = person()
        p.firstname   =  'James'
        p.middlename  =  '<none>'
        p.lastname    =  'Aspey'
        p.email       =  'jaspey@mail.com'
        p.phone       =  '5' *  10

        # Associate the second person with the user
        u.person = p

        # Save user, reload, test that new person was associated
        u.save()
        u = user(u.id)

        self.assertEq(p.id,          u.person.id)
        self.assertEq(p.firstname,   u.person.firstname)
        self.assertEq(p.middlename,  u.person.middlename)
        self.assertEq(p.lastname,    u.person.lastname)
        self.assertEq(p.email,       u.person.email)
        self.assertEq(p.phone,       u.person.phone)

    def it_captures_persons_brokenrules(self):
        p = person()
        p.firstname   =  'Emily'
        p.middlename  =  'Moran'
        p.lastname    =  'Barwick'
        p.email       =  'ebarwick@mail.com'
        p.phone       =  '5' * 256 # broken rule

        u = user()
        u.name      =  str(uuid4())
        u.service   =  str(uuid4())
        u.password  =  str(uuid4())
        u.person = p

        self.assertOne(u.brokenrules)
        self.assertBroken(u, 'phone', 'fits')


    def it_captures_role_mm_object_brokenrules(self):
        u = user()
        u.name      =  str(uuid4())
        u.service   =  str(uuid4())
        u.password  =  str(uuid4())

        rs = roles().ALL()

        u.roles += rs.first

        u.roles.first._id = None # break rule


        try:
            u.save()
        except brokenruleserror as ex:
            self.assertOne(ex.object.brokenrules)
            self.assertBroken(ex.object, 'roleid', 'full')
        except:
            self.assertFail('The wrong exception type was raised')
        else:
            self.assertFail('No exception was raised')


    def it_persists_roles(self):
        rs = roles().ALL()
        rs.sort(key=lambda x: x.name)

        # Create user 
        u = user()
        u.service = str(uuid4())
        u.name = str(uuid4())
        u.password = str(uuid4())

        # Add roles
        for r in 'carapacian-blog-editor', 'carapacian-techblog-editor':
            u.roles += rs[r]

        # Save user
        u.save()

        # Reload user and assert roles were saved and reloaded
        u = user(u.id)
        u.roles.sort(key=lambda x: x.name)

        self.assertTwo(u.roles)
        for i, r in enumerate(u.roles):
            self.assertEq(rs[i].name, r.name)

        # Add an additional roles, save, load and test
        u.roles += rs['vegout-blog-editor']

        u.save()

        u = user(u.id)
        u.roles.sort(key=lambda x: x.name)
        self.assertThree(u.roles)
        for i, r in enumerate(u.roles):
            self.assertEq(rs[i].name, r.name)

        # Remove a roles, one-by-one, reload and test
        for i in range(u.roles.count, 0, -1):
            # Remove
            u.roles.pop()

            # Test
            for j, r in enumerate(u.roles):
                self.assertEq(rs[j].name, r.name)
            self.assertCount(i - 1, u.roles)

            # Save and reload
            u.save()
            u = user(u.id)

            # Test
            u.roles.sort('name')
            self.assertCount(i - 1, u.roles)
            for j, r in enumerate(u.roles):
                self.assertEq(rs[j].name, r.name)

    def it_calls_isassigned(self):
        r = role()
        r.name = 'good-eats-blog-editor'

        u = user()
        u.service   =  str(uuid4())
        u.name      =  str(uuid4())
        u.password  =  str(uuid4())

        u.roles += r

        self.assertTrue(u.isassigned(r))
        self.assertFalse(u.isassigned(role('not-assigned')))

        for t in '', None, 1, True:
            try:
                u.isassigned(t)
            except TypeError:
                pass
            except Exception:
                self.assertFail('Wrong exception type')
            else:
                self.assertFail('No exception thrown')

    def it_prevents_modifications_of_roles(self):
        u = user()
        rs = roles().ALL()
        u.roles += rs['vegout-blog-editor']

        try:
            u.roles.first.name = 'shouldnt-be-doing-this'
        except NotImplementedError:
            pass
        except Exception:
            self.assertFail('Wrong exception type')
        else:
            self.assertFail('No exception was thrown')

        # TODO Capabilities shouldn't be modifiable either. Implement the below.
        if False:
            try:
                u.roles.first.capabilities += 'can-derp'
            except NotImplementedError:
                pass
            except Exception as ex:
                self.assertFail('Wrong exception type')
            else:
                self.assertFail('No exception was thrown')

class test_role(tester):
    def __init__(self):
        super().__init__()
        users().RECREATE()
        roles().RECREATE()

    def it_creates_valid(self):
        r = role()
        r.name = uuid4()

        self.assertZero(r.brokenrules)

    def it_creates(self):
        r = role()
        r.name          =   str(uuid4())
        r.capabilities  +=  str(uuid4())
        r.capabilities  +=  str(uuid4())
        r.save()

    def it_deletes(self):
        r = role()
        r.name          =   str(uuid4())
        r.capabilities  +=  str(uuid4())
        r.capabilities  +=  str(uuid4())
        r.save()

        cnt = r.delete()

        self.assertEq(1, cnt)

        cnt = r.delete()
        self.assertEq(0, cnt)

        try:
            r = person(r.id)
        except Exception:
            pass
        else:
            self.assertFail('No exception thrown')

    def it_loads(self):
        r = role()
        r.name = str(uuid4())
        r.save()

        r1 = role(r.id)
        for p in 'id', 'name':
            self.assertEq(getattr(r, p), getattr(r1, p), 'Property: ' + p)

        self.assertZero(r.capabilities)

        r = role()
        r.name = str(uuid4())
        r.capabilities += str(uuid4())
        r.capabilities += str(uuid4())
        r.save()

        r1 = role(r.id)

        self.assertCount(2, r1.capabilities)

        for cap in r.capabilities:
            found = False
            for cap1 in r1.capabilities:
                if cap.name == cap1.name:
                    found = True
            self.assertTrue(found)

    def it_enforces_uniqueness_constraint_on_name(self):
        # TODO
        pass

    def it_calls_name(self):
        r = role()
        name = str(uuid4())
        r.name = name

        self.assertEq(name, r.name)
        r.save()
        self.assertEq(name, r.name)

        name = str(uuid4())
        r.name = name
        self.assertEq(name, r.name)
        r.save()

        r = role(r.id)
        self.assertEq(name, r.name)

    def it_calls_capabilities(self):
        r = role()
        self.assertZero(r.capabilities)
        self.assertType(capabilities, r.capabilities)
        r.save()

        r = role(r.id)
        self.assertZero(r.capabilities)
        self.assertType(capabilities, r.capabilities)

        r.capabilities += str(uuid4())
        r.capabilities += str(uuid4())
        self.assertCount(2, r.capabilities)
        r.save()
        self.assertCount(2, r.capabilities)

        r1 = role(r.id)
        self.assertCount(2, r1.capabilities)
        self.assertType(capabilities, r1.capabilities)
        for cap in r.capabilities:
            found = False
            for cap1 in r1.capabilities:
                if cap.name == cap1.name:
                    found = True
            self.assertTrue(found)

        r = r1

        r.capabilities += str(uuid4())
        self.assertCount(3, r.capabilities)
        r.save()
        self.assertCount(3, r.capabilities)

        r1 = role(r.id)
        self.assertCount(3, r1.capabilities)
        for cap in r.capabilities:
            found = False
            for cap1 in r1.capabilities:
                if cap.name == cap1.name:
                    found = True
            self.assertTrue(found)

        r = r1
        r.capabilities -= r.capabilities.first
        r.save()

        r1 = role(r.id)

        self.assertCount(2, r1.capabilities)
        for cap in r.capabilities:
            found = False
            for cap1 in r1.capabilities:
                if cap.name == cap1.name:
                    found = True
            self.assertTrue(found)

class test_capabilities(tester):
    
    def it_adds(self):
        # Add zero
        caps = capabilities()

        self.assertZero(caps)
        
        # Add one
        caps += 'edit_posts'

        self.assertOne(caps)
        self.assertEq(caps.first.name, 'edit_posts')

        # Add the same one
        caps += 'edit_posts'

        self.assertOne(caps)
        self.assertEq(caps.first.name, 'edit_posts')

        # Add a second one
        caps += 'add_posts'

        self.assertTwo(caps)
        self.assertEq(caps.first.name, 'edit_posts')
        self.assertEq(caps.second.name, 'add_posts')

    def it_removes(self):
        caps = capabilities()

        # Remove non existing capability
        caps -= 'edit_posts'

        self.assertZero(caps)
        
        # Add one
        caps += 'edit_posts'

        # Remove existing capability
        caps -= 'edit_posts'

        self.assertZero(caps)

        caps += 'edit_posts'
        caps += 'add_posts'

        # Remove one of two
        caps -= 'edit_posts'

        self.assertOne(caps)
        self.assertEq(caps.first.name, 'add_posts')

    def it_call__str__(self):
        caps = capabilities()
        self.assertEmptyString(str(caps))

        caps += 'edit_posts'
        self.assertEq('edit_posts', str(caps))

        caps += 'add_posts'
        self.assertEq('edit_posts add_posts', str(caps))

class test_capability(tester):
    
    def it_breaks_name_rule(self):
        cap = capability('')
        self.assertOne(cap.brokenrules)
        self.assertBroken(cap, 'name', 'full')

        cap = capability(None)
        self.assertCount(1, cap.brokenrules)
        self.assertBroken(cap, 'name', 'full')

        cap = capability(1)
        self.assertOne(cap.brokenrules)
        self.assertBroken(cap, 'name', 'valid')

        cap = capability('can edit')
        self.assertOne(cap.brokenrules)
        self.assertBroken(cap, 'name', 'valid')

        cap = capability(' can-edit ')
        self.assertZero(cap.brokenrules)
    

t = testers()
t.oninvoketest += lambda src, eargs: print('# ', end='', flush=True)
t.oninvoketest += lambda src, eargs: print(eargs.method[0], flush=True)
t.run()
print(t)
