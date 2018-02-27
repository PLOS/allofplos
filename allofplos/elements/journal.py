from collections import OrderedDict


class Journal():
    """For parsing the journal name element of articles, as well as converting DOIs to journal names."""

    def __init__(self, journal_meta_element):
        """Initialize an instance of the journal class."""
        self.element = journal_meta_element

    @staticmethod
    def doi_to_journal(doi):
        """For a given doi, get the PLOS journal that the article is published in.

        For the subset of DOIs with 'annotation' in the name, assumes PLOS ONE.
        :return: string of journal name
        """
        journal_map = OrderedDict([
                                   ('pone', 'PLOS ONE'),
                                   ('pcbi', 'PLOS Computational Biology'),
                                   ('pntd', 'PLOS Neglected Tropical Diseases'),
                                   ('pgen', 'PLOS Genetics'),
                                   ('ppat', 'PLOS Pathogens'),
                                   ('pbio', 'PLOS Biology'),
                                   ('pmed', 'PLOS Medicine'),
                                   ('pctr', 'PLOS Clinical Trials'),
                                   ('annotation', 'PLOS ONE')
                                  ])

        return next(value for key, value in journal_map.items() if key in doi)
    
    def __str__(self):
        """Provides str(Journal()) style access to Journal().parse_plos_journal.
        """
        return self.parse_plos_journal()

    def parse_plos_journal(self, caps_fixed=True):
        """For an individual PLOS article, get the journal it was published in from the article XML.

        Relies on article XML metadata. For DOI to journal conversion, see `doi_to_journal()`.
        :param caps_fixed: whether to render 'PLOS' in the journal name correctly, or as-is ('PLoS')
        :return: PLOS journal name at specified xpath location
        """
        journal = ''
        # location for newer journal articles
        journal_path_1 = self.element.xpath('/journal-title-group/journal-title')
        if len(journal_path_1):
            assert len(journal_path_1) == 1
            journal = journal_path_1[0].text
        else:
            # location for older journal articles
            journal_path_2 = self.element.xpath('/journal-title')
            if len(journal_path_2):
                assert len(journal_path_2) == 1
                journal = journal_path_2[0].text

            else:
                # location for oldest journal articles
                nlm_ta_id = [j for j in self.element.getchildren() if j.attrib.get('journal-id-type', None) == 'nlm-ta']
                assert len(nlm_ta_id) == 1
                journal = nlm_ta_id[0].text

        if caps_fixed:
            journal = journal.split()
            if journal[0].lower() == 'plos':
                journal[0] = "PLOS"
            journal = (' ').join(journal)
        return journal
