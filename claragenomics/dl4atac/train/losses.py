#
# Copyright (c) 2019, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#

import torch
import torch.nn as nn
import torch.nn.functional as F
from collections import Iterable, OrderedDict
from claragenomics.dl4atac.train.custom_losses import PearsonLoss


class MultiLoss(object):
    ''' MultiLoss Object

    Args:
        loss_types: a single string or an interable of strings of loss types;
                    if not provided, the object can only be used for calling it's members
        weights: weight factors for each loss type; default to all 1's if not provided
        device: gpu id to push the loss function to; default to cpu if not provided

    '''

    def __init__(self, loss_types=None, weights=None, device=None):
        self.device = device
        self.loss_types = loss_types
        self.weights = weights

        if self.loss_types:
            if isinstance(self.loss_types, str):
                self.loss_types = [self.loss_types] 
            if not isinstance(self.loss_types, Iterable):
                raise TypeError("loss_types should be a string or an iterable of strings")
        else: # if no loss_types is provided, only instantiate the object to use its members
            return

        # decode loss_types
        if self.weights:
            if not isinstance(self.weights, Iterable):
                self.weights = [self.weights]
        else:
            self.weights = [1] * len(self.loss_types)
        
        if len(self.weights) != len(self.loss_types):
            raise AttributeError("loss_types and weights should have same length.")

        self.losses = OrderedDict()
        for l, w in zip(self.loss_types, self.weights):
            try:
                loss_func = getattr(self, l)()
                self.losses[l] = (loss_func, w)
            except AttributeError as e:
                print(e)
        
    def get_loss_types(self):
        return list(zip(self.loss_types, self.weights))
        
    # L2 loss
    def mse(self):
        loss_func = nn.MSELoss(reduction='mean')
        loss_func = self.to_device(loss_func)
        return loss_func

    # binary cross-entropy loss
    def bce(self):
        loss_func = nn.BCELoss(reduction='mean')
        loss_func = self.to_device(loss_func)
        return loss_func

    # Pearson loss
    def pearsonloss(self):
        loss_func = PearsonLoss()
        loss_func = self.to_device(loss_func)
        return loss_func

    def to_device(self, loss_func):
        #TODO: error checking for self.device
        if self.device:
            loss_func = loss_func.cuda(self.device)
        return loss_func

    def single_output_loss(self, pred, label):
        '''
            Single output loss calculation
            Supports combination of multiple loss types 
        '''
        if pred.shape != label.shape:
            raise ValueError("Input tensors have mismatch shape: {} and {}".format(pred.shape, label.shape))
        loss_values = OrderedDict()
        total_loss = 0
        for loss_name, (loss_func, w) in self.losses.items():
            # print(loss_name, loss_func, w)
            loss = loss_func(pred, label)
            loss_values[loss_name] = loss
            total_loss += loss * w
        
        loss_values['total_loss'] = total_loss
        return total_loss, loss_values

    # MultiLoss a callable object
    def __call__(self, pred, label):
        if not self.loss_types:
            raise ValueError("No valid loss_types provided at instantiation."
                             "You can only call the members of MultiLoss.")
        if isinstance(pred, torch.Tensor):
            if not isinstance(label, torch.Tensor):
                raise TypeError("Type mismatch: {} and {} provided.".format(type(pred), type(label)))
            return self.single_output_loss(pred, label)