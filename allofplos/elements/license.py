import lxml.etree as et
import re

# Creative Commons links
xlink_href = '{http://www.w3.org/1999/xlink}href'
cc_by_4_link = 'https://creativecommons.org/licenses/by/4.0/'
cc_by_3_link = 'https://creativecommons.org/licenses/by/3.0/'
cc0_link = 'https://creativecommons.org/publicdomain/zero/1.0/'
cc_by_3_igo_link = 'https://creativecommons.org/licenses/by/3.0/igo/'
crown_link = 'http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/'
cc_dict = {'CC-BY 4.0': cc_by_4_link,
           'CC-BY 3.0': cc_by_3_link,
           'CC0': cc0_link,
           'CC-BY 3.0 IGO': cc_by_3_igo_link,
           'Crown Copyright': crown_link,
           }


class License():
    """For parsing the license element of articles."""

    def __init__(self, permissions_element, doi):
        """Initialize an instance of the license class."""
        self.element = permissions_element
        self.doi = doi
    
    def __iter__(self):
        """Provides the ability to cast License as a dictionary using 
        dict(License(…)).
        
        Returns a generator of (key, value) tuples, which when passed into 
        dict(), will create the appropriate dictionary. 
        """
        return ((key, value) for key, value in self.license.items())
    
    @property
    def license(self):
        """Dictionary of CC license information from the article license field.
        """
        lic = ''
        cc_link = ''
        copy_year = ''
        copy_holder = ''
        permissions = self.element
        if permissions.xpath('./copyright-year'):
            copy_year = int(permissions.xpath('./copyright-year')[0].text.strip())
        if permissions.xpath('./copyright-holder'):
            try:
                copy_holder = ', '.join([x.text.strip() for x in permissions.xpath('./copyright-holder')])
            except AttributeError:
                print('error getting copyright holder for {}'.format(self.doi))

        license = permissions.xpath('./license')[0]
        if license.attrib.get(xlink_href):
            cc_link = license.attrib[xlink_href]
        elif license.xpath('.//ext-link'):
            link = license.xpath('.//ext-link')[0]
            cc_link = link.attrib[xlink_href]
        if cc_link:
            if cc_link == cc_by_4_link or any(x in cc_link for x in ["Attribution", "4.0"]):
                lic = 'CC-BY 4.0'
            elif cc_link == cc_by_3_igo_link or 'by/3.0/igo' in cc_link:
                lic = 'CC-BY 3.0 IGO'
            elif cc_link == cc_by_3_link or 'by/3.0' in cc_link:
                lic = 'CC-BY 3.0'
            elif cc_link == cc0_link or 'zero/1.0/' in cc_link:
                lic = 'CC0'
            elif cc_link == 'http://www.nationalarchives.gov.uk/doc/open-government-licence/open-government-licence.htm' \
             or 'open-government-licence' in cc_link:
                lic = "Crown Copyright"
            elif cc_link == 'http://www.plos.org/oa/':
                lic = 'CC-BY 3.0 IGO'
            else:
                print('not 4.0', self.doi, link.attrib[xlink_href])
                lic = ''
        else:
            lic = self.parse_license(license)
        lic_dict = {'license': lic,
                    'license_link': cc_dict.get(lic, ''),
                    'copyright_holder': copy_holder,
                    'copyright_year': copy_year}
        return lic_dict

    def parse_license(self, license):
        """For license elements without external links, figure out the appropriate copyright.

        :param license_element: an article XML element with the tag <license>
        :return: license name
        """
        license_text = ' '.join(re.split('\+|\n|\t| ', et.tostring(license, method='text', encoding='unicode')))
        license_text = ''.join(line.lstrip(' \t') for line in license_text.splitlines(True))
        license_text = license_text.replace('\n', ' ').replace('\r', '')
        if any(x in license_text.lower() for x in ["commons attribution license", "creative commons attrib"]):
            lic = 'CC-BY 4.0'
            if any(char.isdigit() for char in license_text):
                digits = [char for char in license_text if char.isdigit()]
                # Flag numbers in case it specifies a CC version number
                print("Number found in CC license string for {}".format(self.doi), digits)
        elif "commons public domain" in license_text.lower() or any(x in license_text for x in ['CC0', 'CCO public', "public domain"]):
            lic = 'CC0'
        elif "creative commons" in license_text.lower():
            print(self.doi, 'unknown CC', license_text)
            lic = ''
        else:
            if 'Public Library of Science Open-Access License' in license_text:
                lic = 'CC-BY 4.0'
            elif "crown copyright" in license_text.lower() or \
             any(x in license_text for x in ['Open Government Licen', 'Public Sector Information Regulations']):
                lic = 'Crown Copyright'
            elif "WHO" in license_text:
                lic = 'CC-BY 3.0 IGO'
            else:
                lic = 'CC-BY 4.0'
        return lic
