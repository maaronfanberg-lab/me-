# Prior art for experiments 8–21

Written 2026-10-28, after experiments 8–21 and before the write-up. These experiments were designed without this
reading, which is a flaw: several of their "findings" are rediscoveries. This file says, claim by claim, what was
already known, what this project adds, and what I could not find either way. Quotes were checked against the
papers' own text (arXiv or proceedings versions).

## Sources read

| short name | paper | what it established that matters here |
|---|---|---|
| Clevert 2016 | Clevert, Unterthiner, Hochreiter, *Fast and Accurate Deep Network Learning by Exponential Linear Units (ELUs)*, ICLR 2016, arXiv:1511.07289 | ReLU's positive mean acts as a bias for the next layer: "Units that have a non-zero mean activation act as bias for the next layer", and "The more the units are correlated, the higher their bias shift." |
| Brock 2021 | Brock, De, Smith, *Characterizing signal propagation to close the performance gap in unnormalized ResNets*, ICLR 2021, arXiv:2101.08692 | In unnormalized residual networks, ReLU induces a **mean shift**: "the squared mean of the hidden activations on each channel grows rapidly as the network depth increases", and the activations for different inputs become "strongly correlated". Such networks are "often unstable" and harder to train with depth. Fix: Scaled Weight Standardization, which centers the weights. |
| De & Smith 2020 | De, Smith, *Batch Normalization Biases Residual Blocks Towards the Identity Function in Deep Networks*, NeurIPS 2020, arXiv:2002.10444 | SkipInit: a learnable scalar on each residual branch, initialized to 0, or to 1/√d or smaller. |
| Zhang 2019 (Fixup) | Zhang, Dauphin, Ma, *Fixup Initialization: Residual Learning Without Normalization*, ICLR 2019, arXiv:1901.09321 | Rescaling, plus zero-initializing the last layer of each residual branch, trains very deep residual networks without normalization. |
| Gotmare 2019 | Gotmare, Keskar, Xiong, Socher, *A Closer Look at Deep Learning Heuristics: Learning Rate Restarts, Warmup and Distillation*, ICLR 2019, arXiv:1810.13243 | **Warm-up mainly protects the layers next to the output.** By CCA, without warm-up the last fully-connected layers change unstably. "Freezing the fully-connected stack for the first 200 iterations" without warm-up gives comparable results (VGG-11; similar for ResNet-18/32 on CIFAR-10). |
| Xiong 2020 | Xiong et al., *On Layer Normalization in the Transformer Architecture*, ICML 2020, arXiv:2002.04745 | In Post-LN transformers, "the expected gradients of the parameters near the output layer are large at initialization", which is why warm-up is needed; Pre-LN removes the need. |
| Gilmer 2022 | Gilmer et al., *A Loss Curvature Perspective on Training Instability in Deep Learning*, ICLR 2022, arXiv:2110.04369 | "Models diverge when the learning rate is too large relative to the 2/λ₁ bound." Warm-up gradually reduces λ₁. But "measuring smoothness at model initialization is not always sufficient to predict whether or not the model will be easily trained." |
| Kalra & Barkeshli 2024 | Kalra, Barkeshli, *Why Warmup the Learning Rate? Underlying Mechanisms and Improvements*, NeurIPS 2024, arXiv:2406.09405 | "the overwhelming benefit of warmup arises from allowing the network to tolerate larger" target learning rates, by guiding training to flatter regions. Large initializations show early "sharpness reduction" through loss catapults. For Adam, the pre-conditioned sharpness is what matters. |
| Kosson 2024 | Kosson et al., *Analyzing & Reducing the Need for Learning Rate Warmup in GPT Training*, NeurIPS 2024, arXiv:2410.23922 | Warm-up keeps the effective update size reasonable. "When the gradients of different samples are highly correlated these internal representations change too fast." For Adam, much of the early excess comes from the β₁ bias correction. |
| Goyal 2017 | Goyal et al., *Accurate, Large Minibatch SGD: Training ImageNet in 1 Hour*, arXiv:1706.02677 | Introduced the now-standard gradual warm-up, "a new warmup scheme that overcomes optimization challenges early in training". |
| Cohen 2021 | Cohen et al., *Gradient Descent on Neural Networks Typically Occurs at the Edge of Stability*, ICLR 2021, arXiv:2103.00065 | Under **full-batch** gradient descent, "the maximum eigenvalue of the training loss Hessian hovers just above" 2/(step size). The runs here use minibatches of 64, so this applies only loosely. |
| Yang 2022 (μP) | Yang et al., *Tensor Programs V: Tuning Large Neural Networks via Zero-Shot Hyperparameter Transfer*, arXiv:2203.03466 | In standard parametrization the output "will blow up with width after 1 step of SGD". μP gives the readout initial variance 1/n² and, for SGD, a learning rate scaled by 1/n. |

## Claim by claim

| this project's claim (experiments) | status against prior art |
|---|---|
| Deep one-matrix residual ReLU piles up a shared vector on the stream; the pile-up grows with depth and breaks training; zero-mean activations don't (8–10, 12, 15) | **Known.** This is Brock 2021's mean shift, and Clevert 2016's bias shift in older form. What this project adds is small: a clean intervention separating mean from gate type (signed ReLU keeps ReLU's exact gates and removes the shift), and a dose–response at fixed depth (the sign-odds dial). |
| The standard two-matrix block does not pile up the same way (17) | **Partly known, and differs in detail.** Brock 2021 finds mean shift even with a convolution after the ReLU, through each weight matrix's non-zero *empirical* mean. Here the two-matrix MLP block grew only 1.3×. The difference is plausibly width, depth and the random-weight scale, but I did not test this, so I make no claim that real two-matrix ResNets are free of mean shift. |
| A short learning-rate warm-up rescues the network (11, 13) | **Known** in general (Goyal et al. 2017; Gilmer 2022; Kalra & Barkeshli 2024). New here only as a fact about this toy: 50 steps is enough. |
| The damaging early steps are the output layer's: warming up the output layer alone rescues (14) | **Known in substance.** Gotmare 2019 found that freezing the final fully-connected layers for the warm-up period works about as well as warm-up. Xiong 2020 locates the problem near the output layer in Post-LN transformers. μP's readout scaling exists because one SGD step on the readout blows the output up. This project replicates the location in a new setting and ties it to a cause: the mean shift makes the readout's input huge. |
| Warming up only the blocks is worse than no warm-up (14) | **Not found in what I read.** Gotmare 2019 froze the final layers, not the earlier ones. Possibly new, possibly unreported. One task, three seeds. |
| Adam avoids the break (18) | **Consistent with known results,** with a caveat. Adam bounds per-parameter steps, so the readout step cannot blow up the way it does under SGD. But Kosson 2024 and Kalra & Barkeshli 2024 show Adam has its own early instabilities that warm-up helps with, so "Adam needs no warm-up" is not a general lesson. |
| Adam's higher transport comes from normalization, not momentum, on digits (21) | **Not found;** narrow and mixed (did not hold on the circle). |
| At matched loss, SGD's transport does not depend on learning rate or momentum (21) | **Not found.** Exploratory, one depth. Its relation to edge-of-stability results (Cohen et al. 2021, where trained sharpness tracks 2/η) is unexamined. Transport is a different quantity from sharpness. |
| The output / transport / gate split of the tilt, and the lapse measurement itself | **The decomposition is elementary chain-rule bookkeeping.** Measuring per-layer gradient norms is standard (signal-propagation plots, Brock 2021). Framing it as a "lapse" is this project's vocabulary, not a new quantity. |

## What remains genuinely open after reading

Three explanations of the output-layer shock appear in the literature, and in these experiments they move
together, because mean shift raises all three:

1. **Readout step size** (μP's argument). One SGD step changes the logits in proportion to η·‖h_L‖², the squared
   size of the readout's input.
2. **Sharpness** (Gilmer 2022, Kalra & Barkeshli 2024). Instability when η·λ₁ > 2.
3. **Correlated gradients** (Kosson 2024). Examples share most of their representation, so updates add up
   coherently.

Experiment 22 measures all three at initialization for every condition run so far. Experiment 23 tests new
conditions chosen so the three predict different outcomes.
