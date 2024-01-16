<div align="center">

# RobustGEC: Robust Grammatical Error Correction Against Subtle Context Perturbation

<div>
  <a href='https://hillzhang1999.github.io/' target='_blank'><b>Yue Zhang</b></a><sup>1</sup>&emsp;
  <a href='https://nealcly.github.io/' target='_blank'>Leyang Cui</b></a><sup>2</sup>&emsp;
  <a href='' target='_blank'>Enbo Zhao</b></a><sup>2</sup>&emsp;
  <a href='https://scholar.google.com/citations?user=aSJcgQMAAAAJ&hl=en/' target='_blank'>Wei Bi</b></a><sup>2</sup>&emsp;
  <a href='https://scholar.google.com/citations?user=Lg31AKMAAAAJ&hl=en/' target='_blank'>Shuming Shi</b></a><sup>2</sup>&emsp;
</div>
<div><sup>1</sup>Soochow University, Suzhou, China</div>
<div><sup>2</sup>Tencent AI Lab</div>

<div>
<h4>

![](https://img.shields.io/badge/PRs-welcome-brightgreen) 
<img src="https://img.shields.io/badge/Version-1.0-blue.svg" alt="Version">
<img src="https://img.shields.io/github/stars/HillZhang1999/RobustGEC?color=yellow" alt="Stars">
<img src="https://img.shields.io/github/issues/HillZhang1999/RobustGEC?color=red" alt="Issues">

</h4>
</div>
</div>

## Introduction

Grammatical Error Correction (GEC) systems play a vital role in assisting people with their daily writing tasks. However, users may sometimes come across a GEC system that initially performs well but fails to correct errors when the inputs are slightly modified. To ensure an ideal user experience, a reliable GEC system should have the ability to provide consistent and accurate suggestions when encountering irrelevant context perturbations, which we refer to as context robustness. In this paper, we introduce RobustGEC, a benchmark designed to evaluate the context robustness of GEC systems. RobustGEC comprises 5,000 GEC cases, each with one original error-correct sentence pair and five variants carefully devised by human annotators. Utilizing RobustGEC, we reveal that state-of-the-art GEC systems still lack sufficient robustness against context perturbations. Moreover, we propose a simple yet effective method for remitting this issue.

If you are interested in our work, please cite:
```bib
@inproceedings{zhang2023robustgec,
  title={RobustGEC: Robust Grammatical Error Correction Against Subtle Context Perturbation},
  author={Zhang, Yue and Cui, Leyang and Zhao, Enbo and Bi, Wei and Shi, Shuming},
  booktitle={Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing},
  pages={16780--16793},
  year={2023}
}
```

## How to Install

You can use the following commands to install the environment for RobustGEC:

```sh
conda create -n robustgec python==3.8
conda activate robustgec
cd ./errant
pip install --editable ./
python3 -m spacy download en_core_web_sm
```

## Evaluation on RobustGEC

First, you can make predictions with your own GEC models on the input file in RobustGEC, such as `./benchmark/bea19/input.txt`.

Then, you should convert the output file to the specific format for evaluation with `convert.py`.
```
O-S My answer is no .
O-T My answer is no .
O-P My answer is no .
A1-S My response is no .
A1-T My response is no .
A1-P My response is no .
A2-S My consequence is no .
A2-T My consequence is no .
A2-P My consequence is no .
A3-S My answer is equivocal .
A3-T My answer is equivocal .
A3-P My answer is equivocal .
A4-S My answer is ambiguous .
A4-T My answer is ambiguous .
A4-P My answer is ambiguous .
A5-S My answer may be no .
A5-T My answer may be no .
A5-P My answer may be no .
```

Finally, you can use `errant_robustgec` command for the final robustness evaluation:
```bash
errant_robustgec -file <file> -evallog <evallog>
```

## Contact

If you have any questions, please feel free to [email](mailto:hillzhang1999@qq.com) me or drop me an issue.