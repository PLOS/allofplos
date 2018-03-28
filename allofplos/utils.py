import textwrap

def dedent(text):
    """Equivalent of textwrap.dedent that ignores unindented first line.
    This means it will still dedent strings like:
    '''foo
    is a bar
    '''
    For use in wrap_paragraphs.
    
    Taken from https://github.com/ipython/ipython_genutils/text.py
    """

    if text.startswith('\n'):
        # text starts with blank line, don't ignore the first line
        return textwrap.dedent(text)

    # split first line
    splits = text.split('\n',1)
    if len(splits) == 1:
        # only one line
        return textwrap.dedent(text)

    first, rest = splits
    # dedent everything but the first line
    rest = textwrap.dedent(rest)
    return '\n'.join([first, rest])
