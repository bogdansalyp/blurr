# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/00_utils.ipynb (unless otherwise specified).

__all__ = ['str_to_class', 'Singleton', 'ModelHelper', 'BLURR_MODEL_HELPER', 'HF_ARCHITECTURES', 'HF_TASKS_ALL',
           'HF_TASKS_AUTO']

# Cell
import sys, inspect
from enum import Enum

import pandas as pd
import torch

from transformers import *
from fastai2.text.all import *

# Cell
def str_to_class(classname):
    "converts string representation to class"
    return getattr(sys.modules[__name__], classname)

# Cell
class Singleton:
    def __init__(self,cls):
        self._cls, self._instance = cls, None

    def __call__(self, *args, **kwargs):
        if self._instance == None: self._instance = self._cls(*args, **kwargs)
        return self._instance

# Cell
@Singleton
class ModelHelper():

    def __init__(self):
        # get hf classes (tokenizers, configs, models, etc...)
        transformer_classes = inspect.getmembers(sys.modules[__name__],
                                                 lambda member: inspect.isclass(member)
                                                 and member.__module__.startswith('transformers.'))

        # build a df that we can query against to get various transformers objects/info
        self._df = pd.DataFrame(transformer_classes, columns=['class_name', 'class_location'])

        # add the module each class is included in
        self._df['module'] = self._df.class_location.apply(lambda v: v.__module__)

        # remove class_location (don't need it anymore)
        self._df.drop(labels=['class_location'], axis=1, inplace=True)

        # break up the module into separate cols
        module_parts_df = self._df.module.str.split(".", n = -1, expand = True)
        for i in range(len(module_parts_df.columns)):
            self._df[f'module_part_{i}'] = module_parts_df[i]

        # using module part 1, break up the functional area and arch into separate cols
        module_part_1_df = self._df.module_part_1.str.split("_", n = 1, expand = True)
        self._df[['functional_area', 'arch']] = module_part_1_df

        # if functional area = modeling, pull out the task it is built for
        model_type_df = self._df[(self._df.functional_area == 'modeling')].class_name.str.split('For', n=1, expand=True)

        model_type_df[1] = np.where(model_type_df[1].notnull(),
                                    'For' + model_type_df[1].astype(str),
                                    model_type_df[1])

        self._df['model_task'] = model_type_df[1]
        self._df['model_task'] = self._df['model_task'].str.replace('For', '', n=1, case=True, regex=False)

        model_type_df = self._df[(self._df.functional_area == 'modeling')].class_name.str.split('With', n=1, expand=True)
        model_type_df[1] = np.where(model_type_df[1].notnull(),
                                    'With' + model_type_df[1].astype(str),
                                    self._df[(self._df.functional_area == 'modeling')].model_task)

        self._df['model_task'] = model_type_df[1]
        self._df['model_task'] = self._df['model_task'].str.replace('With', '', n=1, case=True, regex=False)

        # look at what we're going to remove (use to verify we're just getting rid of stuff we want too)
        # df[~df['hf_class_type'].isin(['modeling', 'configuration', 'tokenization'])]

        # only need these 3 functional areas for our querying purposes
        self._df = self._df[self._df['functional_area'].isin(['modeling', 'configuration', 'tokenization'])]

    def get_architectures(self):
        """Used to get all the architectures supported by your `Transformers` install"""
        return sorted(self._df[(self._df.arch.notna()) &
                        (self._df.arch != None) &
                        (self._df.arch != 'utils')].arch.unique().tolist())

    def get_config(self, arch):
        """Used the locate the name of the configuration class for a given architecture"""
        config = self._df[(self._df.functional_area == 'configuration') &
                          (self._df.arch == arch)].class_name.values[0]

        return str_to_class(config)

    def get_tokenizers(self, arch):
        """Used to get the available huggingface tokenizers for a given architecture. Note: There may be
        multiple tokenizers and so this returns a list.
        """
        toks = sorted(self._df[(self._df.functional_area == 'tokenization') &
                               (self._df.arch == arch)].class_name.values)

        return [str_to_class(tok_name) for tok_name in toks]

    def get_tasks(self, arch=None):
        """Get the type of tasks for which there is a custom model for (*optional: by architecture*).
        There are a number of customized models built for specific tasks like token classification,
        question/answering, LM, etc....
        """
        query = ['model_task.notna()']
        if (arch): query.append(f'arch == "{arch}"')

        return sorted(self._df.query(' & '.join(query), engine='python').model_task.unique().tolist())

    def get_models(self, arch=None, task=None):
        """The transformer models available for use (optional: by architecture | task)"""
        query = ['functional_area == "modeling"']
        if (arch): query.append(f'arch == "{arch}"')
        if (task): query.append(f'model_task == "{task}"')

        models = sorted(self._df.query(' & '.join(query)).class_name.tolist())
        return [str_to_class(model_name) for model_name in models]

    def get_classes_for_model(self, model_name_or_cls):
        """Get tokenizers, config, and model for a given model name / class"""
        model_name = model_name_or_cls if isinstance(model_name_or_cls, str) else model_name_or_cls.__name__

        meta = self._df[self._df.class_name == model_name]
        tokenizers = self.get_tokenizers(meta.arch.values[0])
        config = self.get_config(meta.arch.values[0])

        return (config, tokenizers, str_to_class(model_name))

    def get_model_architecture(self, model_name_or_enum):
        """Get the architecture for a given model name / enum"""
        model_name = model_name_or_enum if isinstance(model_name_or_enum, str) else model_name_or_enum.name
        return self._df[self._df.class_name == model_name].arch.values[0]

    def get_hf_objects(self, pretrained_model_name_or_path, task=None,
                       config=None, tokenizer_cls=None, model_cls=None,
                       config_kwargs={}, tokenizer_kwargs={}, model_kwargs={}, cache_dir=None):
        """Returns the architecture (str), config (obj), tokenizer (obj), and model (obj) given at minimum a
        `pre-trained model name or path`. Specify a `task` to ensure the right "AutoModelFor<task>" is used to
        create the model.

        Optionally, you can pass a config (obj), tokenizer (class), and/or model (class) (along with any
        related kwargs for each) to get as specific as you want w/r/t what huggingface objects are returned.
        """

        # config
        if (config is None):
            config = AutoConfig.from_pretrained(pretrained_model_name_or_path, cache_dir=cache_dir, **config_kwargs)

        # tokenizer
        if (tokenizer_cls is None):
            tokenizer = AutoTokenizer.from_pretrained(pretrained_model_name_or_path,
                                                      cache_dir=cache_dir,
                                                      **tokenizer_kwargs)
        else:
            tokenizer = tokenizer_cls.from_pretrained(pretrained_model_name_or_path,
                                                      cache_dir=cache_dir,
                                                      **tokenizer_kwargs)

        # model
        if (model_cls is None and task is None):
            model = AutoModel.from_pretrained(pretrained_model_name_or_path,
                                              config=config,
                                              cache_dir=cache_dir,
                                              **model_kwargs)
        else:
            if (model_cls is None and task is not None):
                model_cls = self.get_models(arch="auto", task=task.name)[0]

            model = model_cls.from_pretrained(pretrained_model_name_or_path,
                                              config=config,
                                              cache_dir=cache_dir,
                                              **model_kwargs)

        #arch
        arch = self.get_model_architecture(type(model).__name__)

        return (arch, config, tokenizer, model)

# Cell
BLURR_MODEL_HELPER = ModelHelper()

# Cell
HF_ARCHITECTURES = Enum('HF_ARCHITECTURES', BLURR_MODEL_HELPER.get_architectures())

# Cell
HF_TASKS_ALL = Enum('HF_TASKS_ALL', BLURR_MODEL_HELPER.get_tasks())
HF_TASKS_AUTO = Enum('HF_TASKS_AUTO', BLURR_MODEL_HELPER.get_tasks('auto'))