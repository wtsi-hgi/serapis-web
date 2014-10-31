
import unittest

from serapis.domain.models import identifiers


class TestIdentifiers(unittest.TestCase):
    
    
    def test_is_accession_nr(self):
        acc_nr = None
        self.assertRaises(ValueError, identifiers.EntityIdentifier.is_accession_nr, acc_nr)

        acc_nr = 123
        self.assertFalse(identifiers.EntityIdentifier.is_accession_nr(acc_nr))
        
        acc_nr = "123"
        self.assertFalse(identifiers.EntityIdentifier.is_accession_nr(acc_nr))
        
        acc_nr = 123
        self.assertFalse(identifiers.EntityIdentifier.is_accession_nr(acc_nr))

        acc_nr = "ERS216847"
        self.assertTrue(identifiers.EntityIdentifier.is_accession_nr(acc_nr))
        
        acc_nr = "EGAS123"
        self.assertTrue(identifiers.EntityIdentifier.is_accession_nr(acc_nr))
    
    
    def test_is_internal_id(self):
        int_id = 12
        self.assertTrue(identifiers.EntityIdentifier.is_internal_id(int_id))
        
        int_id = 'asd'
        self.assertFalse(identifiers.EntityIdentifier.is_internal_id(int_id))
        
        int_id = "12"
        self.assertTrue(identifiers.EntityIdentifier.is_internal_id(int_id))

    def test_is_name(self):
        name = "john"
        self.assertTrue(identifiers.EntityIdentifier.is_name(name))
        
        name = "Sampl123"
        self.assertTrue(identifiers.EntityIdentifier.is_name(name))

        name = "123"
        self.assertTrue(identifiers.EntityIdentifier.is_name(name))

        name = 123
        self.assertFalse(identifiers.EntityIdentifier.is_name(name))

        name = 'hgi_project'
        self.assertFalse(identifiers.EntityIdentifier.is_name(name))


    def test_guess_identifier_type(self): 
        identif = 123
        id_type = identifiers.EntityIdentifier.guess_identifier_type(identif)
        self.assertEquals(id_type, 'internal_id')
        
        identif = "jane"
        id_type = identifiers.EntityIdentifier.guess_identifier_type(identif)
        self.assertEquals(id_type, 'name')
        
        identif = "EGAS123"
        id_type = identifiers.EntityIdentifier.guess_identifier_type(identif)
        self.assertEquals(id_type, 'accession_number')
        
        identif = "This_should_be_a_name"
        id_type = identifiers.EntityIdentifier.guess_identifier_type(identif)
        self.assertEquals(id_type, 'name')
        
        identif = None
        self.assertRaises(ValueError, identifiers.EntityIdentifier.guess_identifier_type, identif)