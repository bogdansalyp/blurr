# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/01c_data-question-answering.ipynb (unless otherwise specified).

__all__ = ['pre_process_squad', 'HF_QuestionAnswerInput', 'HF_QABatchTransform']

# Cell
import ast
from functools import reduce

from ..utils import *
from .core import *

import torch
from transformers import *
from fastai2.text.all import *

# Cell
def pre_process_squad(row, hf_arch, hf_tokenizer):
    context, qst, ans = row['context'], row['question'], row['answer_text']

    tok_kwargs = {}
    if (hasattr(hf_tokenizer, 'add_prefix_space')): tok_kwargs['add_prefix_space'] = True

    if(hf_tokenizer.padding_side == 'right'):
        tok_input = hf_tokenizer.convert_ids_to_tokens(hf_tokenizer.encode(qst, context, **tok_kwargs))
    else:
        tok_input = hf_tokenizer.convert_ids_to_tokens(hf_tokenizer.encode(context, qst, **tok_kwargs))

    tok_ans = hf_tokenizer.tokenize(str(row['answer_text']), **tok_kwargs)

    start_idx, end_idx = 0,0
    for idx, tok in enumerate(tok_input):
        try:
            if (tok == tok_ans[0] and tok_input[idx:idx + len(tok_ans)] == tok_ans):
                start_idx, end_idx = idx, idx + len(tok_ans)
                break
        except: pass

    row['tokenized_input'] = tok_input
    row['tokenized_input_len'] = len(tok_input)
    row['tok_answer_start'] = start_idx
    row['tok_answer_end'] = end_idx

    return row

# Cell
class HF_QuestionAnswerInput(list): pass

# Cell
class HF_QABatchTransform(HF_BatchTransform):
    def __init__(self, hf_arch, hf_tokenizer, **kwargs):
        super().__init__(hf_arch, hf_tokenizer, HF_QuestionAnswerInput, **kwargs)

    def encodes(self, samples):
        samples = super().encodes(samples)
        for s in samples:
            # cls_index: location of CLS token (used by xlnet and xlm); is a list.index(value) for pytorch tensor's
            s[0]['cls_index'] = (s[0]['input_ids'] == self.hf_tokenizer.cls_token_id).nonzero()[0]
            # p_mask: mask with 1 for token than cannot be in the answer, else 0 (used by xlnet and xlm)
            s[0]['p_mask'] = s[0]['special_tokens_mask']

        return samples

# Cell
@typedispatch
def show_batch(x:HF_QuestionAnswerInput, y, samples, hf_tokenizer=None, ctxs=None, max_n=6, **kwargs):
    res = L()
    for sample, input_ids, start, end in zip(samples, x[0], *y):
        txt = sample[0]
        ans_toks = hf_tokenizer.convert_ids_to_tokens(input_ids, skip_special_tokens=False)[start:end]
        res.append((txt, (start.item(),end.item()), hf_tokenizer.convert_tokens_to_string(ans_toks)))

    display_df(pd.DataFrame(res, columns=['text', 'start/end', 'answer'])[:max_n])
    return ctxs