"""
A model and utilities for greatly easing code generation for nearly any language.

Rationale
---------

Code generation can be a surprisingly complex and tricky topic. When generating very short and trivial scripts (or
config files), you might get away with putting big blocks of code inside strings and crudely joining them together,
potentially throwing in some format specifiers for the few parts that are variable. Once you need to generate longer
and more sophisticated programs (e.g. ORM classes) you will see all sorts of complicated problems pop up.

A core source of complexity is the fact that nearly all serious programs that do code generation are *configurable*.
Which is to say, you cannot know ahead of time the exact structure of the code you will generate. A program that
generates ORM code (i.e. classes that model entries of various types in a database, and automatically synchronize to it)
will work off some config file telling it what all the record types are and what fields they contain. The number of
classes in the final output, as well as the exact code generated for each class, is profoundly influenced by the
contents of the config file. A bit of code that is generated for some class might not be generated for another, because
the corresponding record has some option set or cleared. Some records may be shallow while others may have a complex
nested structure, with the structure of the generated code also following this pattern even though the conversion will
often be achieved by calling the same method.

All this boils down to the conclusion that much of the code that outputs e.g. an array, an object, etc. will often need
to work for a number of elements or a structure that are only known at runtime. And when you can no longer know these
things in advance, all sorts of problems start to pop up:

- The exact rendering of a structure will be influenced (sometimes drastically) by various factors, particularly the
  available horizontal space. For instance, a simple array declaration might look like::

      a = ["one", "two", "three"]

  But if horizontal space is limited (when there are many items and/or the construct occurs nested deep inside some
  other code), we might need a rendering like::

      a = [
          "one", "two",
          "three"
      ]

  Or even::

      a = [
          "one",
          "two",
          "three"
      ]

  Note that the indent size or nature (spaces vs tabs) might also be a configurable option for the generating program,
  which further complicates the rendering.

- The nature of the items inside an array, declaration etc. can also affect the rendering. In particular, if the items
  inside an array are themselves multi-line, then the array itself can only be rendered multi-line, e.g.::

      a = [
          "item",
          {
              "complex": "item",
              "other": "prop
          }
      ]

- When the generation of some bit of code is turned on and off by a runtime option, the effects may be more profound
  than just the deletion of some lines. Whitespace margins around the structure may need to be intelligently collapsed.
  An override method that becomes blank may need to be completely deleted. And so on. This means we can't just
  concatenate rendered structures together, but must deeply model the tree structure of the generated content.

- Since these issues occur for most generated structures, every single code rendering function in your program will have
  a non-trivial degree of complexity, greatly increasing the likelihood that you will fail to consider some edge case
  or some subtle interaction.

- Even if you build up a library of rendering functions for handling all these situations in generating, say,
  JavaScript code, you will need to perform a similar feat for C, C++, Java, etc., which have very similar issues. It
  would be best to come up with a solution that is more abstract than any particular programming language.


The Solution
------------

Enter this package. Instead of returning strings from your renderers, you will instead use the classes provided in
`atmfjstc.lib.abstract_codegen.ast.*` to assemble an AST that describes the output in a structured, language-independent
format. Then, you will call the `.render()` method for the root node (or any subtrees, as desired), which will produce
the full rendered code text while taking care of all the details and subtle interactions. This has many benefits:

- Your renderers can now be vastly simplified. Instead of all the nitty-gritty of text processing, indents, etc., they
  only need concern themselves to converting between your high-level language (JS, etc.) and the intermediate
  representation provided by the abstract_codegen AST.

- Much of your rendering code will now become more functional-like, since often you will be returning an AST directly
  instead of juggling with if's and temporary buffers.

- You can do post-processing on the AST before it gets rendered, so as to eliminate empty methods etc. Since the output
  is well-structured, this is far easier than post-processing text.


Example
-------

::

    def render_squares_array(n):
        ast = Block(
            ItemsList(
                (Atom(str(i*i)) for i in range(1, n+1)),
                joiner=', '
            ),
            'var squares = [', '];'
        )

        print('-' * 60)
        for line in ast.render(CodegenContext(width=60)):
            print(line)


    render_squares_array(10)
    render_squares_array(30)

Result::

    ------------------------------------------------------------
    var squares = [1, 4, 9, 16, 25, 36, 49, 64, 81, 100];
    ------------------------------------------------------------
    var squares = [
      1, 4, 9, 16, 25, 36, 49, 64, 81, 100, 121, 144, 169, 196,
      225, 256, 289, 324, 361, 400, 441, 484, 529, 576, 625,
      676, 729, 784, 841, 900
    ];
"""
