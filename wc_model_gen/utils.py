""" Utility methods for generating submodels

:Author: Yin Hoon Chew <yinhoon.chew@mssm.edu>
:Date: 2019-01-23
:Copyright: 2019, Karr Lab
:License: MIT
"""

from wc_utils.util.ontology import wcm_ontology
from wc_utils.util.units import unit_registry
import math
import wc_lang


def calculate_average_synthesis_rate(mean_concentration, half_life, mean_doubling_time):
	""" Calculate the average synthesis rate of a species over a cell cycle

	    Args:
	    	mean_concentration (:obj:`float`): species mean concentration
	    	half_life (:obj:`float`): species half life
	    	mean_doubling_time (:obj:`float`): mean doubling time of cells

	    Returns:
	    	:obj:`float`: the average synthesis rate of the species
	"""
	ave_synthesis_rate = math.log(2) * (1. / mean_doubling_time + 1. / half_life) * mean_concentration

	return ave_synthesis_rate

def MM_like_rate_law(Avogadro, reaction, modifier, beta):
    """ Generate a Michaelis-Menten-like rate law. For a multi-substrate reaction,  
        the substrate term is formulated as the multiplication of a Hill equation
        with a coefficient of 1 for each substrate.

        Example:

        	Rate = k_cat * [E] * [S1]/(Km_S1 + [S1]) * [S2]/(Km_S2 + [S2])

        	where
        	    k_cat: catalytic constant
            	[E]: concentration of enzyme (modifier)
            	[Sn]: concentration of nth substrate
            	Km_Sn: Michaelis-Menten constant for nth substrate   

        Args:
            Avogadro (:obj:`wc_lang.Parameter`): model parameter for Avogadro number
        	reaction (:obj:`wc_lang.Reaction`): reaction
        	modifier (:obj:`wc_lang.Observable`): an observable that evaluates to the 
        		total concentration of all enzymes that catalyze the reaction
        	beta (:obj:`float`): ratio of Michaelis-Menten constant to substrate 
        		concentration (Km/[S])		

        Returns:
        	:obj:`wc_lang.RateLawExpression`: rate law
        	:obj:`list` of :obj:`wc_lang.Parameter`: list of parameters in the rate law  	
    """
    parameters = []

    model_k_cat = wc_lang.Parameter(id='k_cat_{}'.format(reaction.id),
                                    type=wcm_ontology['WCM:k_cat'],
                                    units=unit_registry.parse_units('s^-1'))
    parameters.append(model_k_cat)

    expression_terms = []
    all_species = []
    for species in reaction.get_reactants():
        all_species.append(species)
        model_k_m = wc_lang.Parameter(id='K_m_{}_{}'.format(reaction.id, species.species_type.id),
                                    type=wcm_ontology['WCM:K_m'],
                                    value=beta * species.distribution_init_concentration.mean,
                                    units=unit_registry.parse_units('M'))
        parameters.append(model_k_m)
        volume = species.compartment.init_density.function_expressions[0].function
        expression_terms.append('({} / ({} + {} * {} * {}))'.format(species.gen_id(),
                                                                    species.gen_id(),
                                                                    model_k_m.id, Avogadro.id,
                                                                    volume.id))

    expression = '{} * {} * {}'.format(model_k_cat.id, modifier.id, ' * '.join(expression_terms))
    
    rate_law = wc_lang.RateLawExpression(expression=expression, 
    									parameters=parameters, 
    									species=all_species, 
    									observables=[modifier])

    return rate_law, parameters 	