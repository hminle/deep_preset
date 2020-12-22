import torch
from torch.optim.optimizer import Optimizer, required

from torch.autograd import Variable
import torch.nn.functional as F
from torch import nn
from torch import Tensor
from torch.nn import Parameter

def get_norm(_name):
    return {
        'evo': EvoNorm2D,
    }[_name]

def instance_std(x, eps=1e-5):
    var = torch.var(x, dim = (2, 3), keepdim=True).expand_as(x)
    if torch.isnan(var).any():
        var = torch.zeros(var.shape)
    return torch.sqrt(var + eps)

def group_std(x, groups = 32, eps = 1e-5):
    N, C, H, W = x.size()
    x = torch.reshape(x, (N, groups, C // groups, H, W))
    var = torch.var(x, dim = (2, 3, 4), keepdim = True).expand_as(x)
    return torch.reshape(torch.sqrt(var + eps), (N, C, H, W))

class EvoNorm2D(nn.Module):
    def __init__(self, input, non_linear = True, version = 'S0', affine = True, momentum = 0.9, eps = 1e-5, training = True):
        super(EvoNorm2D, self).__init__()
        self.non_linear = non_linear
        self.version = version
        self.training = training
        self.momentum = momentum
        self.eps = eps
        if self.version not in ['B0', 'S0']:
            raise ValueError("Invalid EvoNorm version")
        self.insize = input
        self.affine = affine

        if self.affine:
            self.gamma = nn.Parameter(torch.ones(1, self.insize, 1, 1))
            self.beta = nn.Parameter(torch.zeros(1, self.insize, 1, 1))
            if self.non_linear:
                self.v = nn.Parameter(torch.ones(1,self.insize,1,1))
        else:
            self.register_parameter('gamma', None)
            self.register_parameter('beta', None)
            self.register_buffer('v', None)
        self.register_buffer('running_var', torch.ones(1, self.insize, 1, 1))

        self.reset_parameters()

    def reset_parameters(self):
        self.running_var.fill_(1)

    def _check_input_dim(self, x):
        if x.dim() != 4:
            raise ValueError('expected 4D input (got {}D input)'
                             .format(x.dim()))

    def forward(self, x):
        self._check_input_dim(x)
        if self.version == 'S0':
            if self.non_linear:
                num = x * torch.sigmoid(self.v * x)
                return num / group_std(x, eps = self.eps) * self.gamma + self.beta
            else:
                return x * self.gamma + self.beta
        if self.version == 'B0':
            if self.training:
                var = torch.var(x, dim = (0, 2, 3), unbiased = False, keepdim = True)
                self.running_var.mul_(self.momentum)
                self.running_var.add_((1 - self.momentum) * var)
            else:
                var = self.running_var

            if self.non_linear:
                den = torch.max((var+self.eps).sqrt(), self.v * x + instance_std(x, eps = self.eps))
                return x / den * self.gamma + self.beta
            else:
                return x * self.gamma + self.beta
