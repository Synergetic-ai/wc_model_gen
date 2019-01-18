""" Initalize the construction of wc_lang-encoded models from wc_kb-encoded knowledge base.

:Author: Balazs Szigeti <balazs.szigeti@mssm.edu>
:Date: 2018-01-21
:Copyright: 2018, Karr Lab
:License: MIT

TODO:
- read cytosol volume from DB; currently there is only fractional volume?!
"""

from wc_utils.util.chem import EmpiricalFormula
from wc_utils.util.ontology import wcm_ontology
import math
import numpy
import scipy.constants
import wc_kb
import wc_lang
import wc_model_gen


class InitalizeModel(wc_model_gen.ModelComponentGenerator):
    """ Generate compartments """

    def run(self):
        self.gen_compartments()
        self.gen_parameters()
        self.clean_and_validate_options()
        options = self.options

        if options['gen_metabolites']:
            self.gen_metabolites()

        if options['gen_rna']:
            self.gen_rna()

        if options['gen_protein']:
            self.gen_protein()

        if options['gen_complexes']:
            self.gen_complexes()

        if options['gen_distribution_init_concentrations']:
            self.gen_distribution_init_concentrations()

        if options['gen_observables']:
            self.gen_observables()

        if options['gen_kb_reactions']:
            self.gen_kb_reactions()

        if options['gen_kb_rate_laws']:
            self.gen_kb_rate_laws()

    def clean_and_validate_options(self):
        options = self.options

        gen_metabolites = options.get('gen_metabolites', True)
        assert(isinstance(gen_metabolites, bool))
        options['gen_metabolites'] = gen_metabolites

        gen_rna = options.get('gen_rna', True)
        assert(isinstance(gen_rna, bool))
        options['gen_rna'] = gen_rna

        gen_protein = options.get('gen_protein', True)
        assert(isinstance(gen_protein, bool))
        options['gen_protein'] = gen_protein

        gen_complexes = options.get('gen_complexes', True)
        assert(isinstance(gen_complexes, bool))
        options['gen_complexes'] = gen_complexes

        gen_distribution_init_concentrations = options.get('gen_distribution_init_concentrations', True)
        assert(isinstance(gen_distribution_init_concentrations, bool))
        options['gen_distribution_init_concentrations'] = gen_distribution_init_concentrations

        gen_observables = options.get('gen_observables', True)
        assert(isinstance(gen_observables, bool))
        options['gen_observables'] = gen_observables

        gen_kb_reactions = options.get('gen_kb_reactions', True)
        assert(isinstance(gen_kb_reactions, bool))
        options['gen_kb_reactions'] = gen_kb_reactions

        gen_kb_rate_laws = options.get('gen_kb_rate_laws', True)
        assert(isinstance(gen_kb_rate_laws, bool))
        options['gen_kb_rate_laws'] = gen_kb_rate_laws

    def gen_compartments(self):
        # Create default compartments
        kb = self.knowledge_base
        model = self.model

        # TODO: get volume from KB, talk to YH
        c = model.compartments.get_or_create(id='c', name='Cytosol', mean_init_volume=1E-15)
        c.init_density = model.parameters.create(id='density_c', value=1100., units='g l^-1')
        volume_c = model.functions.create(id='volume_c', units='l')
        volume_c.expression, error = wc_lang.FunctionExpression.deserialize(f'{c.id} / {c.init_density.id}', {
            wc_lang.Compartment: {c.id: c},
            wc_lang.Parameter: {c.init_density.id: c.init_density},
            })
        assert error is None, str(error)

        """
        m = model.compartments.get_or_create(id='m', name='Cell membrane', mean_init_volume=1E-10)
        m.init_density = model.parameters.create(id='density_m', value=1100., units='g l^-1')
        volume_m = model.functions.create(id='volume_m', units='l')
        volume_m.expression, error = wc_lang.FunctionExpression.deserialize(f'{m.id} / {m.init_density.id}', {
            wc_lang.Compartment: {m.id: m},
            wc_lang.Parameter: {m.init_density.id: m.init_density},
            })
        assert error is None, str(error)
        """

        e = model.compartments.get_or_create(id='e', name='Extracellular space', mean_init_volume=1E-10)
        e.init_density = model.parameters.create(id='density_e', value=1000., units='g l^-1')
        volume_e = model.functions.create(id='volume_e', units='l')
        volume_e.expression, error = wc_lang.FunctionExpression.deserialize(f'{e.id} / {e.init_density.id}', {
            wc_lang.Compartment: {e.id: e},
            wc_lang.Parameter: {e.init_density.id: e.init_density},
            })
        assert error is None, str(error)

    def gen_parameters(self):
        kb = self.knowledge_base
        model = self.model

        # Create parameters
        model.parameters.get_or_create(id='mean_doubling_time',
                                       type=None,
                                       value=kb.cell.properties.get_one(id='mean_doubling_time').value,
                                       units='s')

    def gen_metabolites(self):
        """ Generate all metabolic species in the cytosol """
        kb = self.knowledge_base
        model = self.model

        kb_species_types = kb.cell.species_types.get(
            __type=wc_kb.core.MetaboliteSpeciesType)

        for kb_species_type in kb_species_types:
            self.gen_species_type(kb_species_type)

    def gen_rna(self):
        """ Generate RNAs in model from knowledge base """
        kb = self.knowledge_base
        model = self.model

        kb_species_types = kb.cell.species_types.get(__type=wc_kb.prokaryote_schema.RnaSpeciesType)

        # Calculate average RNA half-life, will be used if value is missing
        half_lifes = []
        for kb_species_type in kb_species_types:
            if (isinstance(kb_species_type.half_life, float) and
                not kb_species_type.half_life == 0 and
                    not math.isnan(kb_species_type.half_life)):
                half_lifes.append(kb_species_type.half_life)

        avg_rna_half_life = numpy.mean(half_lifes)

        # Create RNA species
        for kb_species_type in kb_species_types:
            if math.isnan(kb_species_type.half_life) or kb_species_type.half_life == 0:
                # TODO: remove; KB should be treated as read only
                kb_species_type.half_life = avg_rna_half_life

            self.gen_species_type(kb_species_type, ['c'])

    def gen_protein(self):
        """ Generate proteins in model from knowledge base """
        kb = self.knowledge_base
        model = self.model

        kb_species_types = kb.cell.species_types.get(__type=wc_kb.prokaryote_schema.ProteinSpeciesType)

        # Calculate average protein half-life, will be used if value is missing
        half_lifes = []
        for kb_species_type in kb_species_types:
            if isinstance(kb_species_type.half_life, float) and \
                    not kb_species_type.half_life == 0 and \
                    not math.isnan(kb_species_type.half_life):
                half_lifes.append(kb_species_type.half_life)

        avg_protein_half_life = numpy.mean(half_lifes)

        for kb_species_type in kb_species_types:
            if math.isnan(kb_species_type.half_life) or kb_species_type.half_life == 0:
                # TODO: remove; KB should be treated as read only
                kb_species_type.half_life = avg_protein_half_life

            self.gen_species_type(kb_species_type, ['c'])

    def gen_complexes(self):
        """ Generate complexes in model from knowledge base """
        kb = self.knowledge_base
        model = self.model

        kb_species_types = kb.cell.species_types.get(__type=wc_kb.core.ComplexSpeciesType)
        for kb_species_type in kb_species_types:
            self.gen_species_type(kb_species_type, ['c'])

    def gen_species_type(self, kb_species_type, extra_compartment_ids=None):
        """ Generate a model species type

        Args:
            kb_species_type (:obj:`wc_kb.SpeciesType`): knowledge base species type
            extra_compartment_ids (:obj:`list` of :obj:`str`, optional): compartment ids of
                additional species that should be created beyond those represented in the KB

        Returns:
            * :obj:`wc_lang.SpeciesType`: model species type
        """

        model = self.model
        model_species_type = model.species_types.get_or_create(id=kb_species_type.id)
        model_species_type.name = kb_species_type.name

        if isinstance(kb_species_type, wc_kb.core.MetaboliteSpeciesType):
            model_species_type.type = wcm_ontology['WCM:metabolite'] # metabolite
            model_species_type.structure = kb_species_type.structure

        elif isinstance(kb_species_type, wc_kb.core.DnaSpeciesType):
            model_species_type.type = wcm_ontology['WCM:DNA'] # DNA
            model_species_type.structure = kb_species_type.get_seq()

        elif isinstance(kb_species_type, wc_kb.prokaryote_schema.RnaSpeciesType):
            model_species_type.type = wcm_ontology['WCM:RNA'] # RNA
            model_species_type.structure = kb_species_type.get_seq()

        elif isinstance(kb_species_type, wc_kb.prokaryote_schema.ProteinSpeciesType):
            model_species_type.type = wcm_ontology['WCM:protein'] # protein
            model_species_type.structure = kb_species_type.get_seq()

        elif isinstance(kb_species_type, wc_kb.core.ComplexSpeciesType):
            model_species_type.type = wcm_ontology['WCM:protein'] # protein
            model_species_type.structure = None

        else:
            raise ValueError('Unsupported species type: {}'.format(
                kb_species_type.__class__.__name__))

        """
        if kb_species_type.get_empirical_formula():
            model_species_type.empirical_formula = EmpiricalFormula(kb_species_type.get_empirical_formula())
        model_species_type.molecular_weight = kb_species_type.get_mol_wt()
        model_species_type.charge = kb_species_type.get_charge()
        model_species_type.comments = kb_species_type.comments
        compartment_ids = set([s.compartment.id for s in kb_species_type.species] +
                              (extra_compartment_ids or []))
         """

        if kb_species_type.get_empirical_formula():
            model_species_type.empirical_formula = EmpiricalFormula(kb_species_type.get_empirical_formula())
        model_species_type.molecular_weight = kb_species_type.get_mol_wt()
        model_species_type.charge = kb_species_type.get_charge()
        model_species_type.comments = kb_species_type.comments
        compartment_ids = set([s.compartment.id for s in kb_species_type.species] +
                              (extra_compartment_ids or []))

        for compartment_id in compartment_ids:
            model_compartment = model.compartments.get_one(id=compartment_id)
            model_species = model.species.get_or_create(species_type=model_species_type, compartment=model_compartment)
            model_species.id = model_species.gen_id()

        return model_species_type

    def gen_distribution_init_concentrations(self):
        """ Generate concentrations in model from knowledge base """
        kb = self.knowledge_base
        model = self.model
        cytosol = model.compartments.get_one(id='c')

        for conc in kb.cell.concentrations:
            species_comp_model = model.compartments.get_one(id=conc.species.compartment.id)

            species_type = model.species_types.get_or_create(id=conc.species.species_type.id)
            species = model.species.get_or_create(species_type=species_type, compartment=species_comp_model)
            species.id = species.gen_id()

            conc = model.distribution_init_concentrations.create(
                species=species,
                mean=conc.value, units=wc_lang.ConcentrationUnit.M,
                comments=conc.comments, references=conc.references)
            conc.id = conc.gen_id()

    def gen_observables(self):
        """ Generate observables in model from knowledge base """
        kb = self.knowledge_base
        model = self.model

        for kb_observable in kb.cell.observables:
            model_observable = model.observables.get_or_create(id=kb_observable.id)            
            model_observable.name = kb_observable.name
            model_observable.expression = wc_lang.ObservableExpression(
                expression=kb_observable.expression.expression)
            
            for kb_species in kb_observable.expression.species:
                kb_species_type = kb_species.species_type
                kb_compartment = kb_species.compartment
                model_species_type = model.species_types.get_one(
                    id=kb_species_type.id)
                model_species = model_species_type.species.get_one(
                    compartment=model.compartments.get_one(id=kb_compartment.id))
                model_observable.expression.species.append(model_species)
                
            for kb_observable_observable in kb_observable.expression.observables:
                model_observable_observable = model.observables.get_or_create(
                    id=kb_observable_observable.id)
                model_observable.expression.observables.append(model_observable_observable)                

    def gen_kb_reactions(self):
        """ Generate reactions encoded within KB """
        kb = self.knowledge_base
        model = self.model

        for kb_rxn in kb.cell.reactions:
            submodel_id = kb_rxn.submodel
            submodel = model.submodels.get_or_create(id=submodel_id)

            model_rxn = model.reactions.create(
                submodel=submodel,
                id=kb_rxn.id + '_kb',
                name=kb_rxn.name,
                reversible=kb_rxn.reversible,
                comments=kb_rxn.comments)

            for participant in kb_rxn.participants:
                kb_species = participant.species
                model_species_type = model.species_types.get_one(id=kb_species.species_type.id)
                model_compartment = model.compartments.get_one(id=kb_species.compartment.id)
                model_species = model_species_type.species.get_one(compartment=model_compartment)

                # ensure that species are present in extracellular space
                if model_species is None:
                    model_species = self.gen_species_type(kb_species.species_type, model_compartment)
                model_rxn.participants.add(
                    model_species.species_coefficients.get_or_create(coefficient=participant.coefficient))

    def gen_kb_rate_laws(self):
        """ Generate rate laws for reactions encoded in KB """
        kb = self.knowledge_base
        model = self.model

        Avogadro = model.parameters.get_or_create(id='Avogadro')
        Avogadro.type = None
        Avogadro.value = scipy.constants.Avogadro
        Avogadro.units = 'molecule mol^-1'

        for kb_rxn in kb.cell.reactions:
            submodel_id = kb_rxn.submodel
            submodel = model.submodels.get_or_create(id=submodel_id)
            model_rxn = submodel.reactions.get_one(id=kb_rxn.id + '_kb')

            for kb_rate_law in kb_rxn.rate_laws:
                model_rate_law = model.rate_laws.create(
                    reaction=model_rxn,
                    direction=wc_lang.RateLawDirection[kb_rate_law.direction.name],
                    comments=kb_rate_law.comments)
                model_rate_law.id = model_rate_law.gen_id()

                objects = {
                    wc_lang.Species: {},
                    wc_lang.Function: {},
                    wc_lang.Parameter: {
                        Avogadro.id: Avogadro,
                    },
                }

                reactant_terms = []
                for part in model_rxn.participants:
                    if part.coefficient < 0:
                        objects[wc_lang.Species][part.species.id] = part.species

                        K_m = model.parameters.create(
                            id='K_m_{}_{}_{}_{}'.format(model_rxn.id, kb_rate_law.direction.name,
                                                        part.species.species_type.id, part.species.compartment.id),
                            type=wcm_ontology['WCM:K_m'],
                            value=kb_rate_law.k_m,
                            units='M')
                        objects[wc_lang.Parameter][K_m.id] = K_m

                        volume = part.species.compartment.init_density.function_expressions[0].function
                        objects[wc_lang.Function][volume.id] = volume

                        reactant_terms.append(' * {} / ({} * {} * {} + {})'.format(
                            part.species.id, K_m.id, Avogadro.id, volume.id, part.species.id,))

                enz_terms = []
                for kb_modifier in kb_rate_law.equation.modifiers:
                    enz_species_type = model.species_types.get_one(id=kb_modifier.species_type.id)
                    enz_compartment = model.compartments.get_one(id=kb_modifier.compartment.id)
                    enz_species = model.species.get_or_create(
                        species_type=enz_species_type, compartment=enz_compartment)
                    enz_species.id = enz_species.gen_id()
                    objects[wc_lang.Species][enz_species.id] = enz_species
                    enz_terms.append(' * ' + enz_species.id)

                k_cat = model.parameters.create(
                    id='k_cat_{}_{}'.format(model_rxn.id, kb_rate_law.direction.name),
                    type=wcm_ontology['WCM:k_cat'],
                    value=kb_rate_law.k_cat,
                    units='molecule^-{} s^-1'.format(len(enz_terms)))
                objects[wc_lang.Parameter][k_cat.id] = k_cat

                model_rate_law.expression, error = wc_lang.RateLawExpression.deserialize(
                    '{}{}{}'.format(k_cat.id, ''.join(enz_terms), ''.join(reactant_terms)),
                    objects)
                assert error is None, str(error)
