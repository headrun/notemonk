import markdown

class SafeImagePattern(markdown.ImagePattern):
    def handleMatch(self, m, doc):
        img_node = markdown.ImagePattern.handleMatch(self, m, doc)
        img_node.setAttribute('class', 'inline-image')

        a_node = doc.createElement('a')
        a_node.setAttribute('href', img_node.attribute_values['src'])
        a_node.appendChild(img_node)

        return a_node

class SafeImageExtension(markdown.Extension):

    def extendMarkdown(self, md, md_globals):
        ps = md.inlinePatterns
        index = None
        for i, p in enumerate(ps):
            if isinstance(p, markdown.ImagePattern):
                index = i
                break

        if index is not None:
            ps[index] = SafeImagePattern(markdown.IMAGE_LINK_RE)

def makeExtension(configs=None):
    return SafeImageExtension(configs=configs)

if __name__ == "__main__":
    import doctest
    doctest.testmod()
