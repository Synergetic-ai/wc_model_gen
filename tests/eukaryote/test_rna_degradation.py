""" Tests of rna degradation submodel generation
:Author: Yin Hoon Chew <yinhoon.chew@mssm.edu>
:Date: 2019-06-11
:Copyright: 2019, Karr Lab
:License: MIT
"""

from wc_model_gen.eukaryote import rna_degradation
from wc_onto import onto as wc_ontology
from wc_utils.util.units import unit_registry
import wc_model_gen.global_vars as gvar
import math
import os
import scipy.constants
import shutil
import tempfile
import unittest
import wc_lang
import wc_kb
import wc_kb_gen


class RnaDegradationSubmodelGeneratorTestCase(unittest.TestCase):

    def setUp(self):

        # Create KB content
        self.tmp_dirname = tempfile.mkdtemp()
        self.sequence_path = os.path.join(self.tmp_dirname, 'test_seq.fasta')
        with open(self.sequence_path, 'w') as f:
            f.write('>chr1\nTTTATGACTCTAGTTTAT\n'
                    '>chrM\nTTTatgaCTCTAGTTTAT\n')

        self.kb = wc_kb.KnowledgeBase()
        cell = self.kb.cell = wc_kb.Cell()

        nucleus = cell.compartments.create(id='n')
        mito = cell.compartments.create(id='m')
        cytoplasm = cell.compartments.create(id='c')

        chr1 = wc_kb.core.DnaSpeciesType(cell=cell, id='chr1', sequence_path=self.sequence_path)
        gene1 = wc_kb.eukaryote.GeneLocus(cell=cell, id='gene1', polymer=chr1, start=1, end=18)
        exon1 = wc_kb.eukaryote.GenericLocus(start=4, end=18)
        transcript1 = wc_kb.eukaryote.TranscriptSpeciesType(cell=cell, id='trans1', 
            name='transcript1', gene=gene1, exons=[exon1])
        transcript1_half_life = wc_kb.core.SpeciesTypeProperty(property='half-life', species_type=transcript1, 
            value='36000.0', value_type=wc_ontology['WC:float'])
        transcript1_spec = wc_kb.core.Species(species_type=transcript1, compartment=cytoplasm)
        transcript1_conc = wc_kb.core.Concentration(cell=cell, species=transcript1_spec, value=10.)

        chrM = wc_kb.core.DnaSpeciesType(cell=cell, id='chrM', sequence_path=self.sequence_path)
        gene2 = wc_kb.eukaryote.GeneLocus(cell=cell, id='gene2', polymer=chrM, start=1, end=18)
        exon2 = wc_kb.eukaryote.GenericLocus(start=1, end=10)
        transcript2 = wc_kb.eukaryote.TranscriptSpeciesType(cell=cell, id='trans2', 
            name='transcript2', gene=gene2, exons=[exon2])
        transcript2_half_life = wc_kb.core.SpeciesTypeProperty(property='half-life', species_type=transcript2, 
            value='15000.0', value_type=wc_ontology['WC:float'])
        transcript2_spec = wc_kb.core.Species(species_type=transcript2, compartment=mito)
        transcript2_conc = wc_kb.core.Concentration(cell=cell, species=transcript2_spec, value=10.)

        transcript3 = wc_kb.eukaryote.TranscriptSpeciesType(cell=cell, id='trans3', 
            name='transcript3', gene=gene2, exons=[exon2])
        transcript3_half_life = wc_kb.core.SpeciesTypeProperty(property='half-life', species_type=transcript3, 
            value='36000.0', value_type=wc_ontology['WC:float'])
        transcript3_spec = wc_kb.core.Species(species_type=transcript3, compartment=mito)
        transcript3_conc = wc_kb.core.Concentration(cell=cell, species=transcript3_spec, value=10.)

        transcript4 = wc_kb.eukaryote.TranscriptSpeciesType(cell=cell, id='trans4', 
            name='transcript4', gene=gene2, exons=[exon2])
        transcript4_half_life = wc_kb.core.SpeciesTypeProperty(property='half-life', species_type=transcript4, 
            value='36000.0', value_type=wc_ontology['WC:float'])
        transcript4_spec = wc_kb.core.Species(species_type=transcript4, compartment=mito)
        transcript4_conc = wc_kb.core.Concentration(cell=cell, species=transcript4_spec, value=0.)

        transcript5 = wc_kb.eukaryote.TranscriptSpeciesType(cell=cell, id='trans5', 
            name='transcript5', gene=gene2)
        transcript5_half_life = wc_kb.core.SpeciesTypeProperty(property='half-life', species_type=transcript5, 
            value='36000.0', value_type=wc_ontology['WC:float'])
        transcript5_spec = wc_kb.core.Species(species_type=transcript5, compartment=mito)
        transcript5_conc = wc_kb.core.Concentration(cell=cell, species=transcript5_spec, value=0.)                   

        # Create initial model content
        self.model = model = wc_lang.Model()
        
        model.parameters.create(id='Avogadro', value = scipy.constants.Avogadro,
                                units = unit_registry.parse_units('molecule mol^-1'))

        compartments = {'n': ('nucleus', 5E-14), 'm': ('mitochondria', 2.5E-14), 'c': ('cytoplasm', 9E-14)}
        for k, v in compartments.items():
            init_volume = wc_lang.core.InitVolume(distribution=wc_ontology['WC:normal_distribution'], 
                    mean=v[1], std=0)
            c = model.compartments.create(id=k, name=v[0], init_volume=init_volume)
            c.init_density = model.parameters.create(id='density_' + k, value=1000, 
                units=unit_registry.parse_units('g l^-1'))
            volume = model.functions.create(id='volume_' + k, units=unit_registry.parse_units('l'))
            volume.expression, error = wc_lang.FunctionExpression.deserialize(f'{c.id} / {c.init_density.id}', {
                wc_lang.Compartment: {c.id: c},
                wc_lang.Parameter: {c.init_density.id: c.init_density},
                })
            assert error is None, str(error)

        for i in cell.species_types.get(__type=wc_kb.eukaryote.TranscriptSpeciesType):
            model_species_type = model.species_types.create(id=i.id, name=i.name)
            model_compartment = model.compartments.get_one(id='m' if 'M' in i.gene.polymer.id else 'c')
            model_species = model.species.get_or_create(species_type=model_species_type, compartment=model_compartment)
            model_species.id = model_species.gen_id()
            conc_model = model.distribution_init_concentrations.create(species=model_species, 
                mean=10., units=unit_registry.parse_units('molecule'))
            conc_model.id = conc_model.gen_id()
        model.distribution_init_concentrations.get_one(id='dist-init-conc-trans4[m]').mean = 0.
        ribo_site_species_type = model.species_types.create(id='trans2_ribosome_binding_site')
        mitochondria = model.compartments.get_one(id='m')
        ribo_site_species = model.species.create(species_type=ribo_site_species_type, compartment=mitochondria)
        ribo_site_species.id = ribo_site_species.gen_id()
        conc_ribo_site_species = model.distribution_init_concentrations.create(
            species=ribo_site_species, mean=20, units=unit_registry.parse_units('molecule'))
        conc_ribo_site_species.id = conc_ribo_site_species.gen_id()
            
        complexes = {'complex1': ('Exosome', ['c', 'n']), 'complex2': ('Exosome variant', ['c', 'n']), 'complex3': ('Mitochondrial Exosome', ['m']),
            'complex4': ('Mitochondrial Exosome variant', ['m'])}
        for k, v in complexes.items():
            model_species_type = model.species_types.get_or_create(id=k, name=v[0])
            for comp in v[1]:
                model_compartment = model.compartments.get_one(id=comp)
                model_species = model.species.get_or_create(species_type=model_species_type, compartment=model_compartment)
                model_species.id = model_species.gen_id()
                conc_model = model.distribution_init_concentrations.create(species=model_species, 
                    mean=100., units=unit_registry.parse_units('molecule'))
                conc_model.id = conc_model.gen_id()

        metabolic_participants = ['amp', 'cmp', 'gmp', 'ump', 'h2o', 'h']
        for i in metabolic_participants:
            model_species_type = model.species_types.create(id=i)
            for c in ['n', 'm', 'c']:
                model_compartment = model.compartments.get_one(id=c)
                model_species = model.species.get_or_create(species_type=model_species_type, compartment=model_compartment)
                model_species.id = model_species.gen_id()
                conc_model = model.distribution_init_concentrations.create(species=model_species, 
                    mean=1500., units=unit_registry.parse_units('molecule'))
                conc_model.id = conc_model.gen_id()

    def tearDown(self):
        shutil.rmtree(self.tmp_dirname)
        gvar.transcript_ntp_usage = {}            

    def test_methods(self):
        
        gen = rna_degradation.RnaDegradationSubmodelGenerator(self.kb, self.model, options={
            'rna_input_seq': {'trans5': 'ACC'},
            'rna_exo_pair': {'trans1': 'Exosome', 'trans2': 'Mitochondrial Exosome', 
                'trans3': 'Mitochondrial Exosome', 'trans4': 'Mitochondrial Exosome',
                'trans5': 'Mitochondrial Exosome'},
            'ribosome_occupancy_width': 4,
            })
        gen.run()

        self.assertEqual(gvar.transcript_ntp_usage['trans1'], {'A': 4, 'U': 7, 'G': 2, 'C': 2, 'len': 15})
        self.assertEqual(gvar.transcript_ntp_usage['trans5'], {'A': 1, 'U': 0, 'G': 0, 'C': 2, 'len': 3})

        # Test gen_reactions
        self.assertEqual([i.id for i in self.model.submodels], ['rna_degradation'])
        self.assertEqual(self.model.submodels.get_one(id='rna_degradation').framework, wc_ontology['WC:next_reaction_method'])
        self.assertEqual(sorted([i.id for i in self.model.reactions]), 
            sorted(['degradation_trans1', 'degradation_trans2', 'degradation_trans3', 'degradation_trans4', 'degradation_trans5']))
        self.assertEqual(sorted([i.name for i in self.model.reactions]), 
            sorted(['degradation of transcript1', 'degradation of transcript2', 'degradation of transcript3', 
                'degradation of transcript4', 'degradation of transcript5']))
        self.assertEqual(set([i.submodel.id for i in self.model.reactions]), set(['rna_degradation']))
        self.assertEqual({i.species.id: i.coefficient for i in self.model.reactions.get_one(id='degradation_trans1').participants}, 
            {'amp[c]': 4, 'cmp[c]': 2, 'gmp[c]': 2, 'ump[c]': 7, 'h[c]': 14, 'h2o[c]': -14, 'trans1[c]': -1})
        self.assertEqual({i.species.id: i.coefficient for i in self.model.reactions.get_one(id='degradation_trans2').participants}, 
            {'amp[m]': 2, 'cmp[m]': 2, 'gmp[m]': 1, 'ump[m]': 5, 'h[m]': 9, 'h2o[m]': -9, 'trans2[m]': -1, 'trans2_ribosome_binding_site[m]': -3})
        self.assertEqual({i.species.id: i.coefficient for i in self.model.reactions.get_one(id='degradation_trans5').participants}, 
            {'amp[m]': 1, 'cmp[m]': 2, 'gmp[m]': 0, 'ump[m]': 0, 'h[m]': 2, 'h2o[m]': -2, 'trans5[m]': -1})
        
        # Test gen_rate_laws
        self.assertEqual(len(self.model.rate_laws), 5)
        self.assertEqual(self.model.rate_laws.get_one(id='degradation_trans1-forward').expression.expression,
            'k_cat_degradation_trans1 * complex1[c] * '
            '(trans1[c] / (trans1[c] + K_m_degradation_trans1_trans1 * Avogadro * volume_c))')
        self.assertEqual(self.model.rate_laws.get_one(id='degradation_trans2-forward').expression.expression,
            'k_cat_degradation_trans2 * complex3[m] * '
            '(trans2[m] / (trans2[m] + K_m_degradation_trans2_trans2 * Avogadro * volume_m))')
        self.assertEqual(self.model.rate_laws.get_one(id='degradation_trans3-forward').expression.expression,
            'k_cat_degradation_trans3 * complex3[m] * '
            '(trans3[m] / (trans3[m] + K_m_degradation_trans3_trans3 * Avogadro * volume_m))')

        for law in self.model.rate_laws:
            self.assertEqual(law.validate(), None)
        
        # Test calibrate_submodel
        self.assertEqual(self.model.parameters.get_one(id='K_m_degradation_trans2_trans2').value, 10/scipy.constants.Avogadro/2.5E-14)
        self.assertEqual(self.model.parameters.get_one(id='K_m_degradation_trans2_trans2').comments, 
            'The value was assumed to be 1.0 times the concentration of trans2 in mitochondria')
        self.assertEqual(self.model.parameters.get_one(id='k_cat_degradation_trans1').value, math.log(2)/36000*10/(0.5*100))
        self.assertEqual(self.model.parameters.get_one(id='k_cat_degradation_trans2').value, math.log(2)/15000*10/(0.5*100))

        self.assertEqual(self.model.parameters.get_one(id='K_m_degradation_trans4_trans4').value, 1e-05)
        self.assertEqual(self.model.parameters.get_one(id='K_m_degradation_trans4_trans4').comments, 
            'The value was assigned to 1e-05 because the concentration of trans4 in mitochondria was zero')
        self.assertEqual(self.model.parameters.get_one(id='k_cat_degradation_trans4').value, math.log(2)/36000*10/(0.5*100))
        self.assertEqual(self.model.parameters.get_one(id='k_cat_degradation_trans4').comments, 
            'Set to the median value because it could not be determined from data')

    def test_global_vars(self):
        gvar.transcript_ntp_usage = {
            'trans2': {'A': 4, 'U': 7, 'G': 2, 'C': 2, 'len': 15},
            'trans5': {'A': 1, 'U': 0, 'G': 0, 'C': 2, 'len': 3},
            }
        gen = rna_degradation.RnaDegradationSubmodelGenerator(self.kb, self.model, options={
            'rna_exo_pair': {'trans1': 'Exosome', 'trans2': 'Mitochondrial Exosome', 
                'trans3': 'Mitochondrial Exosome', 'trans4': 'Mitochondrial Exosome',
                'trans5': 'Mitochondrial Exosome'},
            'ribosome_occupancy_width': 4,    
            })
        gen.run()

        self.assertEqual(gvar.transcript_ntp_usage['trans1'], {'A': 4, 'U': 7, 'G': 2, 'C': 2, 'len': 15})

        self.assertEqual({i.species.id: i.coefficient for i in self.model.reactions.get_one(id='degradation_trans1').participants}, 
            {'amp[c]': 4, 'cmp[c]': 2, 'gmp[c]': 2, 'ump[c]': 7, 'h[c]': 14, 'h2o[c]': -14, 'trans1[c]': -1})
        self.assertEqual({i.species.id: i.coefficient for i in self.model.reactions.get_one(id='degradation_trans2').participants}, 
            {'amp[m]': 4, 'cmp[m]': 2, 'gmp[m]': 2, 'ump[m]': 7, 'h[m]': 14, 'h2o[m]': -14, 'trans2[m]': -1, 'trans2_ribosome_binding_site[m]': -4})
        self.assertEqual({i.species.id: i.coefficient for i in self.model.reactions.get_one(id='degradation_trans5').participants}, 
            {'amp[m]': 1, 'cmp[m]': 2, 'gmp[m]': 0, 'ump[m]': 0, 'h[m]': 2, 'h2o[m]': -2, 'trans5[m]': -1})
