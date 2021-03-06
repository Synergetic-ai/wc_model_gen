""" Generator for models based on KBs for random in silico organisms

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2018-06-11
:Copyright: 2018, Karr Lab
:License: MIT
"""
import wc_model_gen

from .initalize_model import InitalizeModel
from .metabolism import MetabolismSubmodelGenerator
from .transcription import TranscriptionSubmodelGenerator
from .rna_degradation import RnaDegradationSubmodelGenerator
from .translation import TranslationSubmodelGenerator
from .protein_degradation import ProteinDegradationSubmodelGenerator

class ProkaryoteModelGenerator(wc_model_gen.ModelGenerator):
    """ Generator for models based on KBs for random in silico organisms
    """

    DEFAULT_COMPONENT_GENERATORS = (
        InitalizeModel,
        TranscriptionSubmodelGenerator,
        RnaDegradationSubmodelGenerator,
        TranslationSubmodelGenerator,
        ProteinDegradationSubmodelGenerator,
        MetabolismSubmodelGenerator
    )

    def clean_and_validate_options(self):
        """ Apply default options and validate options """
        options = self.options

        id = options.get('id', 'rand_wc_model')
        assert(isinstance(id, str) or id is None)
        options['id'] = id

        name = options.get('name', 'Random whole-cell model')
        assert(isinstance(name, str) or name is None)
        options['name'] = name

        version = options.get('version', wc_model_gen.__version__)
        assert(isinstance(version, str) or version is None)
        options['version'] = version
