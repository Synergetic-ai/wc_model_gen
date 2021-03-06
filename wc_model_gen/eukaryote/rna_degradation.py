""" Generator for rna degradation submodel for eukaryotes
:Author: Yin Hoon Chew <yinhoon.chew@mssm.edu>
:Date: 2019-06-11
:Copyright: 2019, Karr Lab
:License: MIT
"""

from wc_onto import onto as wc_ontology
from wc_utils.util.units import unit_registry
import wc_model_gen.global_vars as gvar
import wc_model_gen.utils as utils
import math
import numpy
import scipy.constants
import wc_kb
import wc_lang
import wc_model_gen


class RnaDegradationSubmodelGenerator(wc_model_gen.SubmodelGenerator):
    """ Generator for rna degradation submodel

        Options:
        * rna_input_seq (:obj:`dict`, optional): a dictionary with RNA ids as keys and 
            sequence strings as values
        * rna_exo_pair (:obj:`dict`): a dictionary of RNA id as key and
            the name of exosome complex that degrades the RNA as value
        * beta (:obj:`float`, optional): ratio of Michaelis-Menten constant 
            to substrate concentration (Km/[S]) for use when estimating 
            Km values, the default value is 1
        * ribosome_occupancy_width (:obj:`int`, optional): number of base-pairs 
            on the mRNA occupied by each bound ribosome, 
            the default value is 27 (9 codons)          
    """

    def clean_and_validate_options(self):
        """ Apply default options and validate options """
        options = self.options

        rna_input_seq = options.get('rna_input_seq', {})
        options['rna_input_seq'] = rna_input_seq

        beta = options.get('beta', 1.)
        options['beta'] = beta

        if 'rna_exo_pair' not in options:
            raise ValueError('The dictionary rna_exo_pair has not been provided')
        else:    
            rna_exo_pair = options['rna_exo_pair']

        ribosome_occupancy_width = options.get('ribosome_occupancy_width', 27)
        options['ribosome_occupancy_width'] = ribosome_occupancy_width    

    def gen_reactions(self):
        """ Generate reactions associated with submodel """
        model = self.model
        cell = self.knowledge_base.cell
        nucleus = model.compartments.get_one(id='n')
        mitochondrion = model.compartments.get_one(id='m')
        cytoplasm = model.compartments.get_one(id='c')

        rna_input_seq = self.options['rna_input_seq']
        
        # Get species involved in reaction
        metabolic_participants = ['amp', 'cmp', 'gmp', 'ump', 'h2o', 'h']
        metabolites = {}
        for met in metabolic_participants:
            met_species_type = model.species_types.get_one(id=met)
            metabolites[met] = {
                'c': met_species_type.species.get_or_create(compartment=cytoplasm, model=model),
                'm': met_species_type.species.get_or_create(compartment=mitochondrion, model=model)
                }

        self.submodel.framework = wc_ontology['WC:next_reaction_method']        

        print('Start generating RNA degradation submodel...')
        # Create reaction for each RNA and get exosome
        rna_exo_pair = self.options.get('rna_exo_pair')
        ribosome_occupancy_width = self.options['ribosome_occupancy_width']
        rna_kbs = cell.species_types.get(__type=wc_kb.eukaryote.TranscriptSpeciesType)
        self._degradation_modifier = {}
        deg_rxn_no = 0
        for rna_kb in rna_kbs:  

            rna_kb_compartment_id = rna_kb.species[0].compartment.id
            if rna_kb_compartment_id == 'c':
                rna_compartment = cytoplasm
                degradation_compartment = cytoplasm
            else:
                rna_compartment = mitochondrion
                degradation_compartment = mitochondrion    
            
            rna_model = model.species_types.get_one(id=rna_kb.id).species.get_one(compartment=rna_compartment)
            reaction = model.reactions.get_or_create(submodel=self.submodel, id='degradation_' + rna_kb.id)
            reaction.name = 'degradation of ' + rna_kb.name
            
            if rna_kb.id in gvar.transcript_ntp_usage:
                ntp_count = gvar.transcript_ntp_usage[rna_kb.id]
            else:
                if rna_kb.id in rna_input_seq:
                    seq = rna_input_seq[rna_kb.id]
                else:    
                    seq = rna_kb.get_seq()
                ntp_count = gvar.transcript_ntp_usage[rna_kb.id] = {
                    'A': seq.upper().count('A'),
                    'C': seq.upper().count('C'),
                    'G': seq.upper().count('G'),
                    'U': seq.upper().count('U'),
                    'len': len(seq)
                    }
            
            # Adding participants to LHS
            reaction.participants.append(rna_model.species_coefficients.get_or_create(coefficient=-1))
            reaction.participants.append(metabolites['h2o'][
                degradation_compartment.id].species_coefficients.get_or_create(coefficient=-(ntp_count['len']-1)))

            ribo_binding_site_st = model.species_types.get_one(id='{}_ribosome_binding_site'.format(rna_kb.id))
            if ribo_binding_site_st:
                ribo_binding_site_species = ribo_binding_site_st.species[0]
                site_per_rna = math.floor(ntp_count['len']/ribosome_occupancy_width) + 1
                reaction.participants.append(ribo_binding_site_species.species_coefficients.get_or_create(
                    coefficient=-site_per_rna))

            # Adding participants to RHS
            reaction.participants.append(metabolites['amp'][
                degradation_compartment.id].species_coefficients.get_or_create(coefficient=ntp_count['A']))
            reaction.participants.append(metabolites['cmp'][
                degradation_compartment.id].species_coefficients.get_or_create(coefficient=ntp_count['C']))
            reaction.participants.append(metabolites['gmp'][
                degradation_compartment.id].species_coefficients.get_or_create(coefficient=ntp_count['G']))
            reaction.participants.append(metabolites['ump'][
                degradation_compartment.id].species_coefficients.get_or_create(coefficient=ntp_count['U']))
            reaction.participants.append(metabolites['h'][
                degradation_compartment.id].species_coefficients.get_or_create(coefficient=ntp_count['len']-1))
                             
            # Assign modifier
            self._degradation_modifier[reaction.name] = model.species_types.get_one(
                name=rna_exo_pair[rna_kb.id]).species.get_one(compartment=degradation_compartment)

            deg_rxn_no += 1
        print('{} RNA degradation reactions have been generated'.format(deg_rxn_no))                
        
    def gen_rate_laws(self):
        """ Generate rate laws for the reactions in the submodel """
        model = self.model        
        cell = self.knowledge_base.cell
        nucleus = model.compartments.get_one(id='n')
        mitochondrion = model.compartments.get_one(id='m')
        cytoplasm = model.compartments.get_one(id='c')

        rate_law_no = 0
        rnas_kb = cell.species_types.get(__type=wc_kb.eukaryote.TranscriptSpeciesType)
        for rna_kb in rnas_kb:

            reaction = self.submodel.reactions.get_one(id='degradation_{}'.format(rna_kb.id))

            rna_kb_compartment_id = rna_kb.species[0].compartment.id
            if rna_kb_compartment_id == 'c':
                degradation_compartment = cytoplasm
            else:
                degradation_compartment = mitochondrion 

            modifier = self._degradation_modifier[reaction.name]

            h2o_species = model.species_types.get_one(id='h2o').species.get_one(
                compartment=degradation_compartment)

            ribo_binding_site_st = model.species_types.get_one(id='{}_ribosome_binding_site'.format(rna_kb.id))
            if ribo_binding_site_st:
                ribo_binding_site_species = ribo_binding_site_st.species[0]
                exclude_substrates = [ribo_binding_site_species, h2o_species]
            else:
                exclude_substrates = [h2o_species]    

            rate_law_exp, _ = utils.gen_michaelis_menten_like_rate_law(
                self.model, reaction, modifiers=[modifier], exclude_substrates=exclude_substrates)
            
            rate_law = self.model.rate_laws.create(
                direction=wc_lang.RateLawDirection.forward,
                type=None,
                expression=rate_law_exp,
                reaction=reaction,
                )
            rate_law.id = rate_law.gen_id()
            rate_law_no += 1

        print('{} rate laws for RNA degradation have been generated'.format(rate_law_no))    

    def calibrate_submodel(self):
        """ Calibrate the submodel using data in the KB """
        
        model = self.model        
        cell = self.knowledge_base.cell
        nucleus = model.compartments.get_one(id='n')
        mitochondrion = model.compartments.get_one(id='m')
        cytoplasm = model.compartments.get_one(id='c')

        beta = self.options.get('beta')

        Avogadro = self.model.parameters.get_or_create(
            id='Avogadro',
            type=None,
            value=scipy.constants.Avogadro,
            units=unit_registry.parse_units('molecule mol^-1'))       

        rnas_kb = cell.species_types.get(__type=wc_kb.eukaryote.TranscriptSpeciesType)
        undetermined_model_kcat = []
        determined_kcat = []
        for rna_kb, reaction in zip(rnas_kb, self.submodel.reactions):

            init_species_counts = {}
        
            modifier_species = self._degradation_modifier[reaction.name]      
            init_species_counts[modifier_species.gen_id()] = modifier_species.distribution_init_concentration.mean
                    
            rna_kb_compartment_id = rna_kb.species[0].compartment.id
            if rna_kb_compartment_id == 'c':
                rna_compartment = cytoplasm
                degradation_compartment = cytoplasm
            else:
                rna_compartment = mitochondrion
                degradation_compartment = mitochondrion 

            rna_reactant = model.species_types.get_one(id=rna_kb.id).species.get_one(compartment=rna_compartment)

            half_life = rna_kb.properties.get_one(property='half-life').get_value()
            mean_concentration = rna_reactant.distribution_init_concentration.mean

            average_rate = utils.calc_avg_deg_rate(mean_concentration, half_life)
            
            for species in reaction.get_reactants():

                init_species_counts[species.gen_id()] = species.distribution_init_concentration.mean

                if model.parameters.get(id='K_m_{}_{}'.format(reaction.id, species.species_type.id)):
                    model_Km = model.parameters.get_one(
                        id='K_m_{}_{}'.format(reaction.id, species.species_type.id))
                    if species.distribution_init_concentration.mean:
                        model_Km.value = beta * species.distribution_init_concentration.mean \
                            / Avogadro.value / species.compartment.init_volume.mean
                        model_Km.comments = 'The value was assumed to be {} times the concentration of {} in {}'.format(
                            beta, species.species_type.id, species.compartment.name)
                    else:
                        model_Km.value = 1e-05
                        model_Km.comments = 'The value was assigned to 1e-05 because the concentration of ' +\
                            '{} in {} was zero'.format(species.species_type.id, species.compartment.name)

            model_kcat = model.parameters.get_one(id='k_cat_{}'.format(reaction.id))

            if average_rate:            
                model_kcat.value = 1.
                eval_rate_law = reaction.rate_laws[0].expression._parsed_expression.eval({
                    wc_lang.Species: init_species_counts,
                    wc_lang.Compartment: {
                        rna_compartment.id: rna_compartment.init_volume.mean * \
                            rna_compartment.init_density.value,
                        degradation_compartment.id: degradation_compartment.init_volume.mean * \
                            degradation_compartment.init_density.value}
                    })
                if eval_rate_law:
                    model_kcat.value = average_rate / eval_rate_law
                    determined_kcat.append(model_kcat.value)
                else:
                    undetermined_model_kcat.append(model_kcat)    
            else:          
                undetermined_model_kcat.append(model_kcat)
        
        median_kcat = numpy.median(determined_kcat)
        for model_kcat in undetermined_model_kcat:
            model_kcat.value = median_kcat
            model_kcat.comments = 'Set to the median value because it could not be determined from data'       

        print('RNA degradation submodel has been generated')           
