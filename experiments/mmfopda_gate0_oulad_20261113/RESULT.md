# MMFOPD-A Gate 0 结果

**判定：PARTIAL**。Gate 1 未执行。

真实 OULAD 行为 + 冻结规则模拟请求；无画像字段外发、无模型API、无GPU。
分数采用固定公布时间假设，非实际部署时间证明。所有区间为测试学生1000次bootstrap、固定模型条件区间。

## 样本与请求

```json
{
  "counts": {
    "disability": {
      "train_n": 3911,
      "train_positive": 424,
      "test_n": 2538,
      "test_positive": 238,
      "missing": 0
    },
    "imd_low20": {
      "train_n": 3790,
      "train_positive": 859,
      "test_n": 2466,
      "test_positive": 575,
      "missing": 193
    },
    "age55plus": {
      "train_n": 3911,
      "train_positive": 17,
      "test_n": 2538,
      "test_positive": 15,
      "missing": 0
    }
  },
  "sklearn": "1.9.0",
  "api_calls": 0,
  "gpu_used": false,
  "bootstrap": 1000,
  "feature_sha256": "c55d2dabe3a3aeca2e4eae5917afd906e3ebb9b177be19bf695c9a5ffbeb00a4",
  "request_sha256": "c193e607f7251caf7cb290144790b68454f8c82a89bcf831c2f9b2ecd42cd724"
}
```

```json
{
  "request_names": [
    "tutoring",
    "review_session",
    "extension",
    "format_dataplus",
    "format_dualpane",
    "format_externalquiz",
    "format_forumng",
    "format_glossary",
    "format_homepage",
    "format_htmlactivity",
    "format_oucollaborate",
    "format_oucontent",
    "format_ouwiki",
    "format_page",
    "format_questionnaire",
    "format_quiz",
    "format_repeatactivity",
    "format_resource",
    "format_subpage",
    "format_url"
  ],
  "types": [
    "dataplus",
    "dualpane",
    "externalquiz",
    "forumng",
    "glossary",
    "homepage",
    "htmlactivity",
    "oucollaborate",
    "oucontent",
    "ouwiki",
    "page",
    "questionnaire",
    "quiz",
    "repeatactivity",
    "resource",
    "subpage",
    "url"
  ],
  "students": 6449,
  "total_requests": 140976,
  "by_request": {
    "tutoring": 11375,
    "review_session": 21389,
    "extension": 3472,
    "format_dataplus": 105,
    "format_dualpane": 1,
    "format_externalquiz": 202,
    "format_forumng": 25008,
    "format_glossary": 636,
    "format_homepage": 11563,
    "format_htmlactivity": 2,
    "format_oucollaborate": 1007,
    "format_oucontent": 39912,
    "format_ouwiki": 165,
    "format_page": 2,
    "format_questionnaire": 59,
    "format_quiz": 12587,
    "format_repeatactivity": 0,
    "format_resource": 3359,
    "format_subpage": 9851,
    "format_url": 281
  },
  "zero_request_students": 1323
}
```

## 主表：真实标签 AUC [95%区间] / 平衡准确率 [95%区间]

| 标签 | 观察方 | 周数 | 模型 | AUC [95%] | BA [95%] |
|---|---|---|---|---|---|
| disability | tutor | 4 | LR | 0.505 [0.484, 0.524] | 0.505 [0.484, 0.524] |
| disability | admin | 4 | LR | 0.505 [0.493, 0.518] | 0.505 [0.493, 0.518] |
| disability | resource | 4 | LR | 0.507 [0.469, 0.547] | 0.512 [0.478, 0.545] |
| disability | tutor+admin | 4 | LR | 0.510 [0.487, 0.533] | 0.506 [0.486, 0.524] |
| disability | tutor+resource | 4 | LR | 0.507 [0.472, 0.546] | 0.503 [0.468, 0.537] |
| disability | admin+resource | 4 | LR | 0.516 [0.479, 0.556] | 0.518 [0.484, 0.550] |
| disability | all3 | 4 | LR | 0.512 [0.476, 0.552] | 0.512 [0.478, 0.546] |
| disability | raw_behavior | 4 | LR | 0.563 [0.526, 0.599] | 0.536 [0.503, 0.568] |
| disability | tutor | 4 | Tree3 | 0.505 [0.484, 0.524] | 0.505 [0.484, 0.524] |
| disability | admin | 4 | Tree3 | 0.505 [0.493, 0.518] | 0.505 [0.493, 0.518] |
| disability | resource | 4 | Tree3 | 0.523 [0.487, 0.556] | 0.526 [0.491, 0.559] |
| disability | tutor+admin | 4 | Tree3 | 0.507 [0.484, 0.530] | 0.505 [0.484, 0.524] |
| disability | tutor+resource | 4 | Tree3 | 0.523 [0.487, 0.556] | 0.526 [0.491, 0.559] |
| disability | admin+resource | 4 | Tree3 | 0.523 [0.487, 0.556] | 0.526 [0.491, 0.559] |
| disability | all3 | 4 | Tree3 | 0.523 [0.487, 0.556] | 0.526 [0.491, 0.559] |
| disability | raw_behavior | 4 | Tree3 | 0.539 [0.503, 0.573] | 0.530 [0.499, 0.563] |
| disability | tutor | 8 | LR | 0.505 [0.484, 0.524] | 0.504 [0.484, 0.524] |
| disability | admin | 8 | LR | 0.516 [0.494, 0.539] | 0.516 [0.494, 0.538] |
| disability | resource | 8 | LR | 0.514 [0.479, 0.552] | 0.497 [0.463, 0.531] |
| disability | tutor+admin | 8 | LR | 0.522 [0.493, 0.550] | 0.516 [0.494, 0.538] |
| disability | tutor+resource | 8 | LR | 0.511 [0.477, 0.550] | 0.506 [0.473, 0.541] |
| disability | admin+resource | 8 | LR | 0.534 [0.496, 0.573] | 0.517 [0.486, 0.551] |
| disability | all3 | 8 | LR | 0.535 [0.498, 0.575] | 0.522 [0.490, 0.556] |
| disability | raw_behavior | 8 | LR | 0.575 [0.541, 0.611] | 0.540 [0.508, 0.570] |
| disability | tutor | 8 | Tree3 | 0.511 [0.490, 0.532] | 0.508 [0.487, 0.526] |
| disability | admin | 8 | Tree3 | 0.516 [0.494, 0.539] | 0.516 [0.494, 0.538] |
| disability | resource | 8 | Tree3 | 0.529 [0.496, 0.564] | 0.533 [0.501, 0.566] |
| disability | tutor+admin | 8 | Tree3 | 0.519 [0.490, 0.547] | 0.514 [0.495, 0.535] |
| disability | tutor+resource | 8 | Tree3 | 0.538 [0.499, 0.573] | 0.531 [0.500, 0.561] |
| disability | admin+resource | 8 | Tree3 | 0.536 [0.502, 0.573] | 0.540 [0.507, 0.574] |
| disability | all3 | 8 | Tree3 | 0.529 [0.493, 0.562] | 0.535 [0.501, 0.570] |
| disability | raw_behavior | 8 | Tree3 | 0.566 [0.531, 0.601] | 0.565 [0.531, 0.598] |
| disability | tutor | 12 | LR | 0.490 [0.467, 0.513] | 0.489 [0.465, 0.512] |
| disability | admin | 12 | LR | 0.533 [0.507, 0.560] | 0.532 [0.507, 0.559] |
| disability | resource | 12 | LR | 0.507 [0.470, 0.545] | 0.508 [0.476, 0.541] |
| disability | tutor+admin | 12 | LR | 0.536 [0.506, 0.567] | 0.531 [0.507, 0.558] |
| disability | tutor+resource | 12 | LR | 0.505 [0.468, 0.545] | 0.492 [0.458, 0.527] |
| disability | admin+resource | 12 | LR | 0.545 [0.505, 0.584] | 0.528 [0.494, 0.560] |
| disability | all3 | 12 | LR | 0.543 [0.505, 0.585] | 0.527 [0.493, 0.561] |
| disability | raw_behavior | 12 | LR | 0.595 [0.559, 0.631] | 0.566 [0.536, 0.599] |
| disability | tutor | 12 | Tree3 | 0.531 [0.507, 0.556] | 0.511 [0.492, 0.530] |
| disability | admin | 12 | Tree3 | 0.533 [0.507, 0.560] | 0.532 [0.507, 0.559] |
| disability | resource | 12 | Tree3 | 0.528 [0.492, 0.562] | 0.534 [0.500, 0.566] |
| disability | tutor+admin | 12 | Tree3 | 0.540 [0.510, 0.574] | 0.531 [0.507, 0.558] |
| disability | tutor+resource | 12 | Tree3 | 0.548 [0.512, 0.581] | 0.538 [0.509, 0.567] |
| disability | admin+resource | 12 | Tree3 | 0.563 [0.527, 0.596] | 0.548 [0.513, 0.580] |
| disability | all3 | 12 | Tree3 | 0.565 [0.529, 0.598] | 0.549 [0.515, 0.582] |
| disability | raw_behavior | 12 | Tree3 | 0.543 [0.509, 0.579] | 0.543 [0.510, 0.576] |
| disability | tutor | full | LR | 0.542 [0.510, 0.576] | 0.536 [0.507, 0.565] |
| disability | admin | full | LR | 0.509 [0.480, 0.539] | 0.507 [0.479, 0.538] |
| disability | resource | full | LR | 0.526 [0.489, 0.559] | 0.529 [0.497, 0.562] |
| disability | tutor+admin | full | LR | 0.538 [0.502, 0.576] | 0.536 [0.509, 0.564] |
| disability | tutor+resource | full | LR | 0.539 [0.502, 0.575] | 0.533 [0.500, 0.564] |
| disability | admin+resource | full | LR | 0.537 [0.500, 0.572] | 0.522 [0.489, 0.555] |
| disability | all3 | full | LR | 0.545 [0.508, 0.584] | 0.528 [0.495, 0.561] |
| disability | raw_behavior | full | LR | 0.572 [0.534, 0.609] | 0.544 [0.514, 0.577] |
| disability | tutor | full | Tree3 | 0.569 [0.535, 0.603] | 0.553 [0.523, 0.583] |
| disability | admin | full | Tree3 | 0.506 [0.478, 0.536] | 0.507 [0.479, 0.537] |
| disability | resource | full | Tree3 | 0.537 [0.498, 0.573] | 0.551 [0.517, 0.584] |
| disability | tutor+admin | full | Tree3 | 0.557 [0.523, 0.592] | 0.548 [0.520, 0.575] |
| disability | tutor+resource | full | Tree3 | 0.548 [0.511, 0.582] | 0.548 [0.515, 0.580] |
| disability | admin+resource | full | Tree3 | 0.537 [0.498, 0.573] | 0.551 [0.517, 0.584] |
| disability | all3 | full | Tree3 | 0.548 [0.511, 0.582] | 0.548 [0.515, 0.580] |
| disability | raw_behavior | full | Tree3 | 0.545 [0.512, 0.578] | 0.522 [0.494, 0.550] |
| imd_low20 | tutor | 4 | LR | 0.506 [0.492, 0.520] | 0.506 [0.492, 0.520] |
| imd_low20 | admin | 4 | LR | 0.505 [0.498, 0.513] | 0.505 [0.498, 0.513] |
| imd_low20 | resource | 4 | LR | 0.552 [0.525, 0.577] | 0.551 [0.528, 0.574] |
| imd_low20 | tutor+admin | 4 | LR | 0.510 [0.495, 0.526] | 0.505 [0.498, 0.513] |
| imd_low20 | tutor+resource | 4 | LR | 0.552 [0.526, 0.577] | 0.549 [0.527, 0.573] |
| imd_low20 | admin+resource | 4 | LR | 0.555 [0.528, 0.582] | 0.550 [0.527, 0.573] |
| imd_low20 | all3 | 4 | LR | 0.553 [0.525, 0.580] | 0.547 [0.523, 0.570] |
| imd_low20 | raw_behavior | 4 | LR | 0.572 [0.545, 0.601] | 0.559 [0.537, 0.583] |
| imd_low20 | tutor | 4 | Tree3 | 0.506 [0.492, 0.520] | 0.506 [0.492, 0.520] |
| imd_low20 | admin | 4 | Tree3 | 0.505 [0.498, 0.513] | 0.505 [0.498, 0.513] |
| imd_low20 | resource | 4 | Tree3 | 0.547 [0.523, 0.573] | 0.534 [0.512, 0.557] |
| imd_low20 | tutor+admin | 4 | Tree3 | 0.500 [0.484, 0.516] | 0.505 [0.498, 0.513] |
| imd_low20 | tutor+resource | 4 | Tree3 | 0.547 [0.523, 0.573] | 0.534 [0.512, 0.557] |
| imd_low20 | admin+resource | 4 | Tree3 | 0.548 [0.523, 0.573] | 0.534 [0.513, 0.558] |
| imd_low20 | all3 | 4 | Tree3 | 0.548 [0.523, 0.573] | 0.534 [0.513, 0.558] |
| imd_low20 | raw_behavior | 4 | Tree3 | 0.554 [0.528, 0.580] | 0.544 [0.520, 0.567] |
| imd_low20 | tutor | 8 | LR | 0.503 [0.488, 0.518] | 0.502 [0.488, 0.517] |
| imd_low20 | admin | 8 | LR | 0.497 [0.486, 0.509] | 0.498 [0.486, 0.509] |
| imd_low20 | resource | 8 | LR | 0.564 [0.536, 0.591] | 0.549 [0.526, 0.573] |
| imd_low20 | tutor+admin | 8 | LR | 0.501 [0.483, 0.519] | 0.505 [0.490, 0.519] |
| imd_low20 | tutor+resource | 8 | LR | 0.565 [0.537, 0.591] | 0.548 [0.524, 0.572] |
| imd_low20 | admin+resource | 8 | LR | 0.565 [0.536, 0.591] | 0.549 [0.527, 0.574] |
| imd_low20 | all3 | 8 | LR | 0.564 [0.536, 0.591] | 0.548 [0.525, 0.573] |
| imd_low20 | raw_behavior | 8 | LR | 0.565 [0.538, 0.592] | 0.542 [0.520, 0.566] |
| imd_low20 | tutor | 8 | Tree3 | 0.509 [0.492, 0.523] | 0.506 [0.490, 0.521] |
| imd_low20 | admin | 8 | Tree3 | 0.504 [0.493, 0.515] | 0.501 [0.490, 0.512] |
| imd_low20 | resource | 8 | Tree3 | 0.552 [0.526, 0.576] | 0.532 [0.510, 0.555] |
| imd_low20 | tutor+admin | 8 | Tree3 | 0.508 [0.492, 0.523] | 0.506 [0.490, 0.521] |
| imd_low20 | tutor+resource | 8 | Tree3 | 0.552 [0.526, 0.576] | 0.532 [0.510, 0.555] |
| imd_low20 | admin+resource | 8 | Tree3 | 0.552 [0.526, 0.576] | 0.532 [0.510, 0.555] |
| imd_low20 | all3 | 8 | Tree3 | 0.552 [0.526, 0.576] | 0.532 [0.510, 0.555] |
| imd_low20 | raw_behavior | 8 | Tree3 | 0.573 [0.548, 0.598] | 0.542 [0.524, 0.560] |
| imd_low20 | tutor | 12 | LR | 0.498 [0.482, 0.514] | 0.503 [0.497, 0.507] |
| imd_low20 | admin | 12 | LR | 0.495 [0.480, 0.510] | 0.496 [0.481, 0.511] |
| imd_low20 | resource | 12 | LR | 0.567 [0.540, 0.594] | 0.545 [0.522, 0.567] |
| imd_low20 | tutor+admin | 12 | LR | 0.491 [0.470, 0.510] | 0.488 [0.468, 0.507] |
| imd_low20 | tutor+resource | 12 | LR | 0.567 [0.540, 0.593] | 0.546 [0.523, 0.569] |
| imd_low20 | admin+resource | 12 | LR | 0.564 [0.535, 0.591] | 0.540 [0.515, 0.563] |
| imd_low20 | all3 | 12 | LR | 0.565 [0.537, 0.592] | 0.542 [0.518, 0.567] |
| imd_low20 | raw_behavior | 12 | LR | 0.559 [0.533, 0.586] | 0.537 [0.514, 0.560] |
| imd_low20 | tutor | 12 | Tree3 | 0.503 [0.496, 0.510] | 0.502 [0.497, 0.508] |
| imd_low20 | admin | 12 | Tree3 | 0.495 [0.480, 0.510] | 0.496 [0.481, 0.511] |
| imd_low20 | resource | 12 | Tree3 | 0.561 [0.534, 0.585] | 0.542 [0.520, 0.564] |
| imd_low20 | tutor+admin | 12 | Tree3 | 0.502 [0.495, 0.509] | 0.501 [0.496, 0.507] |
| imd_low20 | tutor+resource | 12 | Tree3 | 0.561 [0.534, 0.585] | 0.542 [0.520, 0.564] |
| imd_low20 | admin+resource | 12 | Tree3 | 0.561 [0.534, 0.585] | 0.542 [0.520, 0.564] |
| imd_low20 | all3 | 12 | Tree3 | 0.561 [0.534, 0.585] | 0.542 [0.520, 0.564] |
| imd_low20 | raw_behavior | 12 | Tree3 | 0.568 [0.542, 0.594] | 0.556 [0.533, 0.579] |
| imd_low20 | tutor | full | LR | 0.529 [0.505, 0.553] | 0.528 [0.507, 0.549] |
| imd_low20 | admin | full | LR | 0.511 [0.490, 0.531] | 0.512 [0.492, 0.532] |
| imd_low20 | resource | full | LR | 0.583 [0.556, 0.610] | 0.562 [0.539, 0.586] |
| imd_low20 | tutor+admin | full | LR | 0.522 [0.498, 0.547] | 0.528 [0.507, 0.549] |
| imd_low20 | tutor+resource | full | LR | 0.582 [0.555, 0.609] | 0.559 [0.536, 0.582] |
| imd_low20 | admin+resource | full | LR | 0.583 [0.556, 0.609] | 0.567 [0.543, 0.590] |
| imd_low20 | all3 | full | LR | 0.582 [0.555, 0.607] | 0.565 [0.541, 0.589] |
| imd_low20 | raw_behavior | full | LR | 0.570 [0.544, 0.596] | 0.543 [0.520, 0.567] |
| imd_low20 | tutor | full | Tree3 | 0.534 [0.510, 0.555] | 0.533 [0.511, 0.554] |
| imd_low20 | admin | full | Tree3 | 0.503 [0.483, 0.524] | 0.507 [0.488, 0.527] |
| imd_low20 | resource | full | Tree3 | 0.573 [0.548, 0.599] | 0.556 [0.532, 0.580] |
| imd_low20 | tutor+admin | full | Tree3 | 0.538 [0.514, 0.561] | 0.529 [0.508, 0.549] |
| imd_low20 | tutor+resource | full | Tree3 | 0.573 [0.548, 0.599] | 0.556 [0.532, 0.580] |
| imd_low20 | admin+resource | full | Tree3 | 0.573 [0.548, 0.599] | 0.556 [0.532, 0.580] |
| imd_low20 | all3 | full | Tree3 | 0.573 [0.548, 0.599] | 0.556 [0.532, 0.580] |
| imd_low20 | raw_behavior | full | Tree3 | 0.570 [0.546, 0.596] | 0.546 [0.527, 0.565] |
| age55plus | tutor | 4 | LR | 0.454 [0.345, 0.554] | 0.454 [0.345, 0.554] |
| age55plus | admin | 4 | LR | 0.515 [0.512, 0.518] | 0.515 [0.512, 0.518] |
| age55plus | resource | 4 | LR | 0.533 [0.370, 0.684] | 0.559 [0.435, 0.690] |
| age55plus | tutor+admin | 4 | LR | 0.466 [0.353, 0.567] | 0.468 [0.359, 0.567] |
| age55plus | tutor+resource | 4 | LR | 0.538 [0.371, 0.708] | 0.561 [0.438, 0.693] |
| age55plus | admin+resource | 4 | LR | 0.560 [0.398, 0.706] | 0.562 [0.438, 0.692] |
| age55plus | all3 | 4 | LR | 0.547 [0.383, 0.714] | 0.597 [0.478, 0.725] |
| age55plus | raw_behavior | 4 | LR | 0.666 [0.486, 0.828] | 0.688 [0.552, 0.819] |
| age55plus | tutor | 4 | Tree3 | 0.454 [0.345, 0.554] | 0.454 [0.345, 0.554] |
| age55plus | admin | 4 | Tree3 | 0.515 [0.512, 0.518] | 0.515 [0.512, 0.518] |
| age55plus | resource | 4 | Tree3 | 0.600 [0.457, 0.732] | 0.580 [0.457, 0.700] |
| age55plus | tutor+admin | 4 | Tree3 | 0.468 [0.359, 0.567] | 0.468 [0.359, 0.567] |
| age55plus | tutor+resource | 4 | Tree3 | 0.562 [0.389, 0.728] | 0.609 [0.482, 0.732] |
| age55plus | admin+resource | 4 | Tree3 | 0.600 [0.457, 0.732] | 0.580 [0.457, 0.700] |
| age55plus | all3 | 4 | Tree3 | 0.566 [0.394, 0.730] | 0.611 [0.485, 0.735] |
| age55plus | raw_behavior | 4 | Tree3 | 0.647 [0.492, 0.789] | 0.652 [0.514, 0.779] |
| age55plus | tutor | 8 | LR | 0.457 [0.346, 0.558] | 0.458 [0.349, 0.558] |
| age55plus | admin | 8 | LR | 0.539 [0.533, 0.544] | 0.539 [0.533, 0.544] |
| age55plus | resource | 8 | LR | 0.627 [0.444, 0.791] | 0.657 [0.532, 0.774] |
| age55plus | tutor+admin | 8 | LR | 0.487 [0.372, 0.592] | 0.492 [0.383, 0.592] |
| age55plus | tutor+resource | 8 | LR | 0.611 [0.422, 0.784] | 0.662 [0.539, 0.779] |
| age55plus | admin+resource | 8 | LR | 0.648 [0.469, 0.803] | 0.663 [0.537, 0.778] |
| age55plus | all3 | 8 | LR | 0.629 [0.446, 0.796] | 0.667 [0.541, 0.783] |
| age55plus | raw_behavior | 8 | LR | 0.745 [0.621, 0.862] | 0.690 [0.565, 0.818] |
| age55plus | tutor | 8 | Tree3 | 0.458 [0.349, 0.558] | 0.458 [0.349, 0.558] |
| age55plus | admin | 8 | Tree3 | 0.539 [0.533, 0.544] | 0.539 [0.533, 0.544] |
| age55plus | resource | 8 | Tree3 | 0.562 [0.415, 0.704] | 0.550 [0.414, 0.673] |
| age55plus | tutor+admin | 8 | Tree3 | 0.492 [0.383, 0.592] | 0.492 [0.383, 0.592] |
| age55plus | tutor+resource | 8 | Tree3 | 0.562 [0.415, 0.704] | 0.550 [0.414, 0.673] |
| age55plus | admin+resource | 8 | Tree3 | 0.562 [0.415, 0.704] | 0.550 [0.414, 0.673] |
| age55plus | all3 | 8 | Tree3 | 0.562 [0.415, 0.704] | 0.550 [0.414, 0.673] |
| age55plus | raw_behavior | 8 | Tree3 | 0.671 [0.514, 0.826] | 0.663 [0.540, 0.803] |
| age55plus | tutor | 12 | LR | 0.470 [0.359, 0.571] | 0.471 [0.362, 0.571] |
| age55plus | admin | 12 | LR | 0.561 [0.555, 0.568] | 0.561 [0.555, 0.568] |
| age55plus | resource | 12 | LR | 0.582 [0.397, 0.752] | 0.667 [0.541, 0.785] |
| age55plus | tutor+admin | 12 | LR | 0.514 [0.400, 0.618] | 0.520 [0.411, 0.618] |
| age55plus | tutor+resource | 12 | LR | 0.590 [0.404, 0.767] | 0.669 [0.545, 0.785] |
| age55plus | admin+resource | 12 | LR | 0.626 [0.452, 0.784] | 0.671 [0.548, 0.787] |
| age55plus | all3 | 12 | LR | 0.624 [0.446, 0.792] | 0.673 [0.550, 0.790] |
| age55plus | raw_behavior | 12 | LR | 0.735 [0.585, 0.872] | 0.697 [0.571, 0.822] |
| age55plus | tutor | 12 | Tree3 | 0.471 [0.362, 0.571] | 0.471 [0.362, 0.571] |
| age55plus | admin | 12 | Tree3 | 0.561 [0.555, 0.568] | 0.561 [0.555, 0.568] |
| age55plus | resource | 12 | Tree3 | 0.609 [0.450, 0.743] | 0.621 [0.499, 0.749] |
| age55plus | tutor+admin | 12 | Tree3 | 0.520 [0.411, 0.618] | 0.520 [0.411, 0.618] |
| age55plus | tutor+resource | 12 | Tree3 | 0.609 [0.450, 0.743] | 0.621 [0.499, 0.749] |
| age55plus | admin+resource | 12 | Tree3 | 0.609 [0.450, 0.743] | 0.621 [0.499, 0.749] |
| age55plus | all3 | 12 | Tree3 | 0.609 [0.450, 0.743] | 0.621 [0.499, 0.749] |
| age55plus | raw_behavior | 12 | Tree3 | 0.643 [0.496, 0.801] | 0.640 [0.518, 0.775] |
| age55plus | tutor | full | LR | 0.490 [0.350, 0.622] | 0.497 [0.387, 0.597] |
| age55plus | admin | full | LR | 0.575 [0.463, 0.651] | 0.581 [0.481, 0.651] |
| age55plus | resource | full | LR | 0.682 [0.505, 0.836] | 0.703 [0.570, 0.826] |
| age55plus | tutor+admin | full | LR | 0.550 [0.413, 0.700] | 0.534 [0.408, 0.657] |
| age55plus | tutor+resource | full | LR | 0.687 [0.513, 0.841] | 0.673 [0.550, 0.789] |
| age55plus | admin+resource | full | LR | 0.669 [0.521, 0.823] | 0.652 [0.522, 0.785] |
| age55plus | all3 | full | LR | 0.659 [0.501, 0.822] | 0.656 [0.524, 0.787] |
| age55plus | raw_behavior | full | LR | 0.693 [0.543, 0.843] | 0.603 [0.486, 0.739] |
| age55plus | tutor | full | Tree3 | 0.629 [0.495, 0.765] | 0.577 [0.466, 0.676] |
| age55plus | admin | full | Tree3 | 0.581 [0.481, 0.651] | 0.581 [0.481, 0.651] |
| age55plus | resource | full | Tree3 | 0.625 [0.461, 0.777] | 0.605 [0.487, 0.734] |
| age55plus | tutor+admin | full | Tree3 | 0.572 [0.422, 0.726] | 0.534 [0.408, 0.657] |
| age55plus | tutor+resource | full | Tree3 | 0.630 [0.465, 0.783] | 0.609 [0.490, 0.736] |
| age55plus | admin+resource | full | Tree3 | 0.662 [0.515, 0.805] | 0.615 [0.499, 0.747] |
| age55plus | all3 | full | Tree3 | 0.665 [0.520, 0.806] | 0.617 [0.501, 0.749] |
| age55plus | raw_behavior | full | Tree3 | 0.614 [0.494, 0.721] | 0.546 [0.479, 0.649] |

## 合谋增量（最佳单方在同标签、周数、模型内选取）

| 标签 | 周数 | 模型 | 最佳单方 | 三方 AUC | 差值 [配对95%] |
|---|---|---|---|---|---|
| disability | 4 | LR | resource (0.507) | 0.512 | 0.005 [-0.031, 0.015] |
| disability | 4 | Tree3 | resource (0.523) | 0.523 | 0.000 [-0.024, 0.000] |
| disability | 8 | LR | admin (0.516) | 0.535 | 0.019 [-0.016, 0.034] |
| disability | 8 | Tree3 | resource (0.529) | 0.529 | -0.000 [-0.044, 0.032] |
| disability | 12 | LR | admin (0.533) | 0.543 | 0.011 [-0.023, 0.037] |
| disability | 12 | Tree3 | admin (0.533) | 0.565 | 0.032 [-0.011, 0.050] |
| disability | full | LR | tutor (0.542) | 0.545 | 0.003 [-0.039, 0.029] |
| disability | full | Tree3 | tutor (0.569) | 0.548 | -0.022 [-0.064, 0.012] |
| imd_low20 | 4 | LR | resource (0.552) | 0.553 | 0.001 [-0.006, 0.007] |
| imd_low20 | 4 | Tree3 | resource (0.547) | 0.548 | 0.001 [-0.005, 0.007] |
| imd_low20 | 8 | LR | resource (0.564) | 0.564 | -0.000 [-0.004, 0.004] |
| imd_low20 | 8 | Tree3 | resource (0.552) | 0.552 | 0.000 [0.000, 0.000] |
| imd_low20 | 12 | LR | resource (0.567) | 0.565 | -0.002 [-0.009, 0.003] |
| imd_low20 | 12 | Tree3 | resource (0.561) | 0.561 | 0.000 [-0.000, 0.000] |
| imd_low20 | full | LR | resource (0.583) | 0.582 | -0.001 [-0.008, 0.005] |
| imd_low20 | full | Tree3 | resource (0.573) | 0.573 | 0.000 [0.000, 0.000] |
| age55plus | 4 | LR | resource (0.533) | 0.547 | 0.014 [-0.132, 0.062] |
| age55plus | 4 | Tree3 | resource (0.600) | 0.566 | -0.033 [-0.188, 0.111] |
| age55plus | 8 | LR | resource (0.627) | 0.629 | 0.002 [-0.095, 0.041] |
| age55plus | 8 | Tree3 | resource (0.562) | 0.562 | 0.000 [-0.126, 0.000] |
| age55plus | 12 | LR | resource (0.582) | 0.624 | 0.042 [-0.117, 0.067] |
| age55plus | 12 | Tree3 | resource (0.609) | 0.609 | 0.000 [-0.110, 0.000] |
| age55plus | full | LR | resource (0.682) | 0.659 | -0.023 [-0.173, 0.065] |
| age55plus | full | Tree3 | tutor (0.629) | 0.665 | 0.036 [-0.170, 0.113] |

## 标签置乱下界

| 标签 | 观察方 | 周数 | 模型 | AUC [95%] | BA [95%] |
|---|---|---|---|---|---|
| disability | tutor | 4 | LR | 0.493 [0.474, 0.512] | 0.493 [0.474, 0.512] |
| disability | admin | 4 | LR | 0.496 [0.487, 0.505] | 0.496 [0.487, 0.505] |
| disability | resource | 4 | LR | 0.515 [0.477, 0.552] | 0.516 [0.491, 0.539] |
| disability | tutor+admin | 4 | LR | 0.489 [0.468, 0.512] | 0.489 [0.468, 0.512] |
| disability | tutor+resource | 4 | LR | 0.504 [0.465, 0.538] | 0.516 [0.491, 0.539] |
| disability | admin+resource | 4 | LR | 0.510 [0.473, 0.548] | 0.516 [0.491, 0.539] |
| disability | all3 | 4 | LR | 0.501 [0.463, 0.536] | 0.516 [0.491, 0.539] |
| disability | raw_behavior | 4 | LR | 0.488 [0.446, 0.526] | 0.513 [0.479, 0.545] |
| disability | tutor | 4 | Tree3 | 0.493 [0.474, 0.512] | 0.493 [0.474, 0.512] |
| disability | admin | 4 | Tree3 | 0.496 [0.487, 0.505] | 0.496 [0.487, 0.505] |
| disability | resource | 4 | Tree3 | 0.511 [0.487, 0.532] | 0.513 [0.489, 0.535] |
| disability | tutor+admin | 4 | Tree3 | 0.489 [0.468, 0.512] | 0.489 [0.468, 0.512] |
| disability | tutor+resource | 4 | Tree3 | 0.511 [0.487, 0.532] | 0.513 [0.489, 0.535] |
| disability | admin+resource | 4 | Tree3 | 0.511 [0.487, 0.532] | 0.513 [0.489, 0.535] |
| disability | all3 | 4 | Tree3 | 0.511 [0.487, 0.532] | 0.513 [0.489, 0.535] |
| disability | raw_behavior | 4 | Tree3 | 0.513 [0.494, 0.532] | 0.506 [0.490, 0.522] |
| disability | tutor | 8 | LR | 0.490 [0.471, 0.510] | 0.489 [0.470, 0.509] |
| disability | admin | 8 | LR | 0.504 [0.488, 0.524] | 0.504 [0.488, 0.523] |
| disability | resource | 8 | LR | 0.491 [0.452, 0.529] | 0.498 [0.465, 0.529] |
| disability | tutor+admin | 8 | LR | 0.499 [0.473, 0.525] | 0.498 [0.472, 0.524] |
| disability | tutor+resource | 8 | LR | 0.477 [0.435, 0.515] | 0.480 [0.446, 0.512] |
| disability | admin+resource | 8 | LR | 0.493 [0.454, 0.529] | 0.501 [0.468, 0.532] |
| disability | all3 | 8 | LR | 0.483 [0.442, 0.521] | 0.487 [0.456, 0.517] |
| disability | raw_behavior | 8 | LR | 0.493 [0.458, 0.529] | 0.491 [0.459, 0.523] |
| disability | tutor | 8 | Tree3 | 0.496 [0.477, 0.515] | 0.493 [0.474, 0.512] |
| disability | admin | 8 | Tree3 | 0.504 [0.488, 0.524] | 0.504 [0.488, 0.523] |
| disability | resource | 8 | Tree3 | 0.510 [0.497, 0.525] | 0.510 [0.502, 0.516] |
| disability | tutor+admin | 8 | Tree3 | 0.497 [0.477, 0.517] | 0.495 [0.475, 0.515] |
| disability | tutor+resource | 8 | Tree3 | 0.510 [0.497, 0.525] | 0.510 [0.502, 0.516] |
| disability | admin+resource | 8 | Tree3 | 0.510 [0.497, 0.525] | 0.510 [0.502, 0.516] |
| disability | all3 | 8 | Tree3 | 0.510 [0.497, 0.525] | 0.510 [0.502, 0.516] |
| disability | raw_behavior | 8 | Tree3 | 0.506 [0.494, 0.519] | 0.503 [0.492, 0.512] |
| disability | tutor | 12 | LR | 0.486 [0.466, 0.507] | 0.486 [0.465, 0.506] |
| disability | admin | 12 | LR | 0.498 [0.479, 0.521] | 0.498 [0.478, 0.520] |
| disability | resource | 12 | LR | 0.496 [0.457, 0.532] | 0.500 [0.468, 0.530] |
| disability | tutor+admin | 12 | LR | 0.489 [0.463, 0.515] | 0.491 [0.465, 0.516] |
| disability | tutor+resource | 12 | LR | 0.486 [0.448, 0.523] | 0.484 [0.452, 0.514] |
| disability | admin+resource | 12 | LR | 0.494 [0.456, 0.531] | 0.497 [0.465, 0.529] |
| disability | all3 | 12 | LR | 0.484 [0.446, 0.520] | 0.484 [0.451, 0.514] |
| disability | raw_behavior | 12 | LR | 0.491 [0.452, 0.529] | 0.509 [0.477, 0.544] |
| disability | tutor | 12 | Tree3 | 0.492 [0.473, 0.512] | 0.490 [0.471, 0.509] |
| disability | admin | 12 | Tree3 | 0.498 [0.479, 0.521] | 0.498 [0.478, 0.520] |
| disability | resource | 12 | Tree3 | 0.511 [0.493, 0.528] | 0.510 [0.495, 0.527] |
| disability | tutor+admin | 12 | Tree3 | 0.492 [0.473, 0.512] | 0.490 [0.471, 0.509] |
| disability | tutor+resource | 12 | Tree3 | 0.511 [0.493, 0.528] | 0.510 [0.495, 0.527] |
| disability | admin+resource | 12 | Tree3 | 0.511 [0.493, 0.528] | 0.510 [0.495, 0.527] |
| disability | all3 | 12 | Tree3 | 0.511 [0.493, 0.528] | 0.510 [0.495, 0.527] |
| disability | raw_behavior | 12 | Tree3 | 0.523 [0.508, 0.537] | 0.519 [0.505, 0.532] |
| disability | tutor | full | LR | 0.502 [0.468, 0.534] | 0.511 [0.478, 0.544] |
| disability | admin | full | LR | 0.502 [0.469, 0.531] | 0.504 [0.473, 0.532] |
| disability | resource | full | LR | 0.501 [0.466, 0.537] | 0.489 [0.460, 0.519] |
| disability | tutor+admin | full | LR | 0.509 [0.471, 0.542] | 0.502 [0.469, 0.533] |
| disability | tutor+resource | full | LR | 0.499 [0.463, 0.533] | 0.485 [0.452, 0.516] |
| disability | admin+resource | full | LR | 0.501 [0.464, 0.537] | 0.494 [0.465, 0.524] |
| disability | all3 | full | LR | 0.500 [0.463, 0.536] | 0.493 [0.461, 0.524] |
| disability | raw_behavior | full | LR | 0.497 [0.453, 0.535] | 0.512 [0.478, 0.545] |
| disability | tutor | full | Tree3 | 0.514 [0.484, 0.545] | 0.507 [0.481, 0.535] |
| disability | admin | full | Tree3 | 0.509 [0.479, 0.539] | 0.507 [0.477, 0.536] |
| disability | resource | full | Tree3 | 0.520 [0.488, 0.553] | 0.514 [0.484, 0.545] |
| disability | tutor+admin | full | Tree3 | 0.503 [0.483, 0.523] | 0.502 [0.486, 0.518] |
| disability | tutor+resource | full | Tree3 | 0.511 [0.478, 0.545] | 0.507 [0.476, 0.536] |
| disability | admin+resource | full | Tree3 | 0.512 [0.480, 0.543] | 0.506 [0.477, 0.533] |
| disability | all3 | full | Tree3 | 0.503 [0.483, 0.523] | 0.502 [0.486, 0.518] |
| disability | raw_behavior | full | Tree3 | 0.502 [0.495, 0.508] | 0.504 [0.497, 0.509] |
| imd_low20 | tutor | 4 | LR | 0.502 [0.488, 0.517] | 0.502 [0.488, 0.517] |
| imd_low20 | admin | 4 | LR | 0.504 [0.496, 0.513] | 0.504 [0.496, 0.513] |
| imd_low20 | resource | 4 | LR | 0.489 [0.465, 0.515] | 0.487 [0.465, 0.509] |
| imd_low20 | tutor+admin | 4 | LR | 0.508 [0.492, 0.525] | 0.508 [0.492, 0.524] |
| imd_low20 | tutor+resource | 4 | LR | 0.491 [0.467, 0.517] | 0.488 [0.465, 0.510] |
| imd_low20 | admin+resource | 4 | LR | 0.496 [0.469, 0.522] | 0.486 [0.463, 0.509] |
| imd_low20 | all3 | 4 | LR | 0.499 [0.472, 0.525] | 0.487 [0.465, 0.511] |
| imd_low20 | raw_behavior | 4 | LR | 0.496 [0.468, 0.522] | 0.508 [0.486, 0.529] |
| imd_low20 | tutor | 4 | Tree3 | 0.502 [0.488, 0.517] | 0.502 [0.488, 0.517] |
| imd_low20 | admin | 4 | Tree3 | 0.504 [0.496, 0.513] | 0.504 [0.496, 0.513] |
| imd_low20 | resource | 4 | Tree3 | 0.503 [0.483, 0.522] | 0.497 [0.482, 0.512] |
| imd_low20 | tutor+admin | 4 | Tree3 | 0.510 [0.495, 0.526] | 0.509 [0.493, 0.525] |
| imd_low20 | tutor+resource | 4 | Tree3 | 0.503 [0.483, 0.522] | 0.497 [0.482, 0.512] |
| imd_low20 | admin+resource | 4 | Tree3 | 0.503 [0.483, 0.522] | 0.497 [0.482, 0.512] |
| imd_low20 | all3 | 4 | Tree3 | 0.503 [0.483, 0.522] | 0.497 [0.482, 0.512] |
| imd_low20 | raw_behavior | 4 | Tree3 | 0.498 [0.489, 0.507] | 0.501 [0.494, 0.508] |
| imd_low20 | tutor | 8 | LR | 0.500 [0.485, 0.515] | 0.500 [0.485, 0.515] |
| imd_low20 | admin | 8 | LR | 0.517 [0.504, 0.531] | 0.517 [0.503, 0.531] |
| imd_low20 | resource | 8 | LR | 0.498 [0.471, 0.525] | 0.513 [0.488, 0.536] |
| imd_low20 | tutor+admin | 8 | LR | 0.522 [0.504, 0.540] | 0.520 [0.502, 0.539] |
| imd_low20 | tutor+resource | 8 | LR | 0.498 [0.471, 0.525] | 0.516 [0.492, 0.538] |
| imd_low20 | admin+resource | 8 | LR | 0.515 [0.488, 0.541] | 0.510 [0.486, 0.533] |
| imd_low20 | all3 | 8 | LR | 0.515 [0.488, 0.542] | 0.515 [0.494, 0.538] |
| imd_low20 | raw_behavior | 8 | LR | 0.502 [0.475, 0.529] | 0.499 [0.476, 0.524] |
| imd_low20 | tutor | 8 | Tree3 | 0.501 [0.485, 0.515] | 0.500 [0.485, 0.515] |
| imd_low20 | admin | 8 | Tree3 | 0.508 [0.495, 0.521] | 0.512 [0.500, 0.526] |
| imd_low20 | resource | 8 | Tree3 | 0.487 [0.463, 0.512] | 0.490 [0.468, 0.512] |
| imd_low20 | tutor+admin | 8 | Tree3 | 0.517 [0.498, 0.536] | 0.518 [0.501, 0.536] |
| imd_low20 | tutor+resource | 8 | Tree3 | 0.490 [0.466, 0.514] | 0.491 [0.469, 0.513] |
| imd_low20 | admin+resource | 8 | Tree3 | 0.512 [0.488, 0.537] | 0.507 [0.485, 0.528] |
| imd_low20 | all3 | 8 | Tree3 | 0.512 [0.487, 0.537] | 0.507 [0.484, 0.527] |
| imd_low20 | raw_behavior | 8 | Tree3 | 0.498 [0.474, 0.522] | 0.501 [0.477, 0.523] |
| imd_low20 | tutor | 12 | LR | 0.505 [0.489, 0.522] | 0.504 [0.499, 0.508] |
| imd_low20 | admin | 12 | LR | 0.518 [0.501, 0.535] | 0.518 [0.501, 0.534] |
| imd_low20 | resource | 12 | LR | 0.511 [0.483, 0.536] | 0.510 [0.488, 0.533] |
| imd_low20 | tutor+admin | 12 | LR | 0.522 [0.502, 0.544] | 0.518 [0.499, 0.539] |
| imd_low20 | tutor+resource | 12 | LR | 0.513 [0.485, 0.536] | 0.506 [0.483, 0.529] |
| imd_low20 | admin+resource | 12 | LR | 0.523 [0.496, 0.548] | 0.519 [0.496, 0.540] |
| imd_low20 | all3 | 12 | LR | 0.524 [0.498, 0.549] | 0.521 [0.498, 0.544] |
| imd_low20 | raw_behavior | 12 | LR | 0.497 [0.470, 0.524] | 0.494 [0.471, 0.516] |
| imd_low20 | tutor | 12 | Tree3 | 0.507 [0.492, 0.523] | 0.503 [0.489, 0.519] |
| imd_low20 | admin | 12 | Tree3 | 0.506 [0.489, 0.523] | 0.511 [0.496, 0.527] |
| imd_low20 | resource | 12 | Tree3 | 0.495 [0.470, 0.519] | 0.491 [0.468, 0.514] |
| imd_low20 | tutor+admin | 12 | Tree3 | 0.520 [0.504, 0.536] | 0.517 [0.501, 0.532] |
| imd_low20 | tutor+resource | 12 | Tree3 | 0.487 [0.463, 0.511] | 0.490 [0.466, 0.514] |
| imd_low20 | admin+resource | 12 | Tree3 | 0.495 [0.470, 0.519] | 0.491 [0.468, 0.514] |
| imd_low20 | all3 | 12 | Tree3 | 0.487 [0.463, 0.511] | 0.490 [0.466, 0.514] |
| imd_low20 | raw_behavior | 12 | Tree3 | 0.508 [0.488, 0.529] | 0.507 [0.487, 0.527] |
| imd_low20 | tutor | full | LR | 0.509 [0.484, 0.533] | 0.512 [0.489, 0.534] |
| imd_low20 | admin | full | LR | 0.518 [0.496, 0.541] | 0.514 [0.493, 0.536] |
| imd_low20 | resource | full | LR | 0.497 [0.468, 0.524] | 0.500 [0.477, 0.522] |
| imd_low20 | tutor+admin | full | LR | 0.506 [0.480, 0.532] | 0.511 [0.488, 0.535] |
| imd_low20 | tutor+resource | full | LR | 0.499 [0.469, 0.527] | 0.504 [0.480, 0.527] |
| imd_low20 | admin+resource | full | LR | 0.489 [0.460, 0.516] | 0.501 [0.476, 0.524] |
| imd_low20 | all3 | full | LR | 0.494 [0.465, 0.522] | 0.503 [0.478, 0.526] |
| imd_low20 | raw_behavior | full | LR | 0.492 [0.466, 0.520] | 0.493 [0.472, 0.516] |
| imd_low20 | tutor | full | Tree3 | 0.506 [0.482, 0.529] | 0.505 [0.483, 0.525] |
| imd_low20 | admin | full | Tree3 | 0.504 [0.483, 0.527] | 0.508 [0.488, 0.530] |
| imd_low20 | resource | full | Tree3 | 0.494 [0.474, 0.514] | 0.496 [0.476, 0.516] |
| imd_low20 | tutor+admin | full | Tree3 | 0.496 [0.474, 0.517] | 0.499 [0.478, 0.520] |
| imd_low20 | tutor+resource | full | Tree3 | 0.494 [0.474, 0.514] | 0.496 [0.476, 0.516] |
| imd_low20 | admin+resource | full | Tree3 | 0.494 [0.474, 0.514] | 0.496 [0.476, 0.516] |
| imd_low20 | all3 | full | Tree3 | 0.494 [0.474, 0.514] | 0.496 [0.476, 0.516] |
| imd_low20 | raw_behavior | full | Tree3 | 0.498 [0.475, 0.518] | 0.498 [0.475, 0.518] |
| age55plus | tutor | 4 | LR | 0.512 [0.443, 0.610] | 0.512 [0.443, 0.610] |
| age55plus | admin | 4 | LR | 0.481 [0.408, 0.517] | 0.481 [0.408, 0.517] |
| age55plus | resource | 4 | LR | 0.525 [0.373, 0.665] | 0.494 [0.360, 0.629] |
| age55plus | tutor+admin | 4 | LR | 0.496 [0.391, 0.607] | 0.481 [0.408, 0.517] |
| age55plus | tutor+resource | 4 | LR | 0.526 [0.377, 0.669] | 0.504 [0.370, 0.634] |
| age55plus | admin+resource | 4 | LR | 0.480 [0.341, 0.617] | 0.501 [0.365, 0.629] |
| age55plus | all3 | 4 | LR | 0.483 [0.337, 0.624] | 0.476 [0.338, 0.601] |
| age55plus | raw_behavior | 4 | LR | 0.513 [0.396, 0.626] | 0.489 [0.375, 0.613] |
| age55plus | tutor | 4 | Tree3 | 0.512 [0.443, 0.610] | 0.512 [0.443, 0.610] |
| age55plus | admin | 4 | Tree3 | 0.481 [0.408, 0.517] | 0.481 [0.408, 0.517] |
| age55plus | resource | 4 | Tree3 | 0.572 [0.411, 0.709] | 0.580 [0.460, 0.680] |
| age55plus | tutor+admin | 4 | Tree3 | 0.496 [0.391, 0.607] | 0.481 [0.408, 0.517] |
| age55plus | tutor+resource | 4 | Tree3 | 0.572 [0.411, 0.709] | 0.580 [0.460, 0.680] |
| age55plus | admin+resource | 4 | Tree3 | 0.572 [0.411, 0.709] | 0.580 [0.460, 0.680] |
| age55plus | all3 | 4 | Tree3 | 0.572 [0.411, 0.709] | 0.580 [0.460, 0.680] |
| age55plus | raw_behavior | 4 | Tree3 | 0.490 [0.349, 0.634] | 0.483 [0.354, 0.613] |
| age55plus | tutor | 8 | LR | 0.509 [0.439, 0.608] | 0.508 [0.439, 0.606] |
| age55plus | admin | 8 | LR | 0.531 [0.459, 0.632] | 0.528 [0.459, 0.629] |
| age55plus | resource | 8 | LR | 0.535 [0.384, 0.687] | 0.503 [0.399, 0.621] |
| age55plus | tutor+admin | 8 | LR | 0.546 [0.432, 0.673] | 0.543 [0.436, 0.662] |
| age55plus | tutor+resource | 8 | LR | 0.538 [0.384, 0.687] | 0.503 [0.400, 0.619] |
| age55plus | admin+resource | 8 | LR | 0.544 [0.375, 0.693] | 0.503 [0.399, 0.619] |
| age55plus | all3 | 8 | LR | 0.531 [0.364, 0.683] | 0.470 [0.370, 0.582] |
| age55plus | raw_behavior | 8 | LR | 0.543 [0.383, 0.683] | 0.557 [0.433, 0.684] |
| age55plus | tutor | 8 | Tree3 | 0.520 [0.452, 0.617] | 0.515 [0.445, 0.613] |
| age55plus | admin | 8 | Tree3 | 0.531 [0.459, 0.632] | 0.528 [0.459, 0.629] |
| age55plus | resource | 8 | Tree3 | 0.404 [0.264, 0.536] | 0.452 [0.382, 0.551] |
| age55plus | tutor+admin | 8 | Tree3 | 0.556 [0.445, 0.681] | 0.548 [0.441, 0.667] |
| age55plus | tutor+resource | 8 | Tree3 | 0.404 [0.264, 0.536] | 0.452 [0.382, 0.551] |
| age55plus | admin+resource | 8 | Tree3 | 0.404 [0.264, 0.536] | 0.452 [0.382, 0.551] |
| age55plus | all3 | 8 | Tree3 | 0.404 [0.264, 0.536] | 0.452 [0.382, 0.551] |
| age55plus | raw_behavior | 8 | Tree3 | 0.496 [0.354, 0.623] | 0.495 [0.366, 0.623] |
| age55plus | tutor | 12 | LR | 0.510 [0.438, 0.612] | 0.506 [0.504, 0.509] |
| age55plus | admin | 12 | LR | 0.546 [0.438, 0.666] | 0.539 [0.438, 0.650] |
| age55plus | resource | 12 | LR | 0.446 [0.310, 0.571] | 0.489 [0.359, 0.618] |
| age55plus | tutor+admin | 12 | LR | 0.563 [0.446, 0.680] | 0.540 [0.439, 0.651] |
| age55plus | tutor+resource | 12 | LR | 0.482 [0.335, 0.609] | 0.490 [0.360, 0.618] |
| age55plus | admin+resource | 12 | LR | 0.454 [0.299, 0.598] | 0.469 [0.336, 0.596] |
| age55plus | all3 | 12 | LR | 0.472 [0.321, 0.616] | 0.473 [0.339, 0.600] |
| age55plus | raw_behavior | 12 | LR | 0.550 [0.373, 0.709] | 0.555 [0.428, 0.675] |
| age55plus | tutor | 12 | Tree3 | 0.504 [0.413, 0.571] | 0.503 [0.407, 0.573] |
| age55plus | admin | 12 | Tree3 | 0.481 [0.370, 0.595] | 0.506 [0.437, 0.607] |
| age55plus | resource | 12 | Tree3 | 0.496 [0.389, 0.591] | 0.508 [0.397, 0.606] |
| age55plus | tutor+admin | 12 | Tree3 | 0.503 [0.403, 0.606] | 0.516 [0.447, 0.615] |
| age55plus | tutor+resource | 12 | Tree3 | 0.496 [0.389, 0.591] | 0.508 [0.397, 0.606] |
| age55plus | admin+resource | 12 | Tree3 | 0.496 [0.389, 0.591] | 0.508 [0.397, 0.606] |
| age55plus | all3 | 12 | Tree3 | 0.496 [0.389, 0.591] | 0.508 [0.397, 0.606] |
| age55plus | raw_behavior | 12 | Tree3 | 0.505 [0.389, 0.616] | 0.476 [0.347, 0.604] |
| age55plus | tutor | full | LR | 0.526 [0.374, 0.680] | 0.494 [0.371, 0.615] |
| age55plus | admin | full | LR | 0.570 [0.436, 0.714] | 0.554 [0.431, 0.686] |
| age55plus | resource | full | LR | 0.525 [0.379, 0.663] | 0.521 [0.386, 0.651] |
| age55plus | tutor+admin | full | LR | 0.555 [0.375, 0.727] | 0.579 [0.455, 0.712] |
| age55plus | tutor+resource | full | LR | 0.518 [0.371, 0.656] | 0.505 [0.371, 0.636] |
| age55plus | admin+resource | full | LR | 0.524 [0.374, 0.662] | 0.495 [0.361, 0.626] |
| age55plus | all3 | full | LR | 0.505 [0.353, 0.639] | 0.511 [0.378, 0.643] |
| age55plus | raw_behavior | full | LR | 0.612 [0.445, 0.780] | 0.631 [0.509, 0.751] |
| age55plus | tutor | full | Tree3 | 0.516 [0.382, 0.637] | 0.503 [0.384, 0.615] |
| age55plus | admin | full | Tree3 | 0.528 [0.491, 0.600] | 0.520 [0.485, 0.592] |
| age55plus | resource | full | Tree3 | 0.480 [0.351, 0.598] | 0.486 [0.353, 0.607] |
| age55plus | tutor+admin | full | Tree3 | 0.463 [0.329, 0.596] | 0.459 [0.340, 0.579] |
| age55plus | tutor+resource | full | Tree3 | 0.480 [0.351, 0.598] | 0.486 [0.353, 0.607] |
| age55plus | admin+resource | full | Tree3 | 0.483 [0.352, 0.601] | 0.488 [0.354, 0.609] |
| age55plus | all3 | full | Tree3 | 0.483 [0.352, 0.601] | 0.488 [0.354, 0.609] |
| age55plus | raw_behavior | full | Tree3 | 0.524 [0.387, 0.662] | 0.519 [0.387, 0.643] |

## 解释边界

本结果只检验请求与敏感标签的相关推断，不是自进化投毒、教学效用或新防御算法证据。
三方模型与单方模型均固定；增加信息并不保证有限样本拟合AUC增加。
3标签×4截点×2模型为探索性多重比较；无多重校正，不声称确认性显著发现。
课程分组诊断见 course_diagnostics.csv；课程/学期不作为攻击特征，但请求可能间接携带课程差异。
没有独立跨课程/跨学期复现。请求规则和分数延时假设限制外推；资源基准仅用训练学生。
原始行为对照是信息更丰富的参照，不是浅模型可达到的数学上界。
逐学生 CSV/请求/原始ID与标签仅保存在本机 var，不公开上传。

## 关键数字与决定理由

按事前门槛判 **PARTIAL（部分通过）**，不是三方合谋 PASS，也不是把部分通过改成失败。

- 唯一满足单方点估计 AUC≥0.65 的配置：age55plus / resource / 全学期 / LR，
  AUC **0.6816 [0.5053, 0.8362]**，BA **0.7029 [0.5703, 0.8256]**。
  训练正例17/3911、测试正例15/2538；AUC下界仅略高于0.5，不能称为稳定确立的单方风险。
  部分通过门槛本身没有规定区间下界，故严格保留 PARTIAL。
- 同标签全学期 LR 三方 AUC **0.6586 [0.5008, 0.8224]**，
  相对最佳单方差 **−0.0229 [−0.1728, 0.0654]**，没有累积增益证据。
- 全学期 age55plus / Tree3 三方 AUC **0.6646 [0.5198, 0.8061]**，
  点差 **+0.0355 [−0.1697, 0.1128]**；尽管点估计与增量达标，
  三方AUC区间下界未超过0.55，所以不通过。
- disability 最佳三方 AUC **0.5645**（第12周 Tree3）；
  imd_low20 最佳三方 AUC **0.5816**（全学期 LR）；均不满足0.65门槛。
- 标签置乱AUC范围：disability 0.4769–0.5227；imd_low20 0.4873–0.5242；
  age55plus 0.4040–0.6120。年龄样本稀少时随机下界也明显波动，不能只挑点估计解释。
- 原始行为对照的 age55plus 第8周 LR AUC **0.7448 [0.6211, 0.8622]**；
  信息更丰富的行为记录可能有年龄信号，但该结果不满足“仅凭请求且有三方增量”的闸门。

**行动：不进入 Gate 1，不开发多Agent合谋防御。** 按部分通过条款仅保留单接收方线索；
如后续开展，应先取得更多55+独立测试样本验证，不能把当前稀少正例结果当作新防御算法准入。
本轮不追加样本、不改课程、不改规则、不更换标签、不运行新配置。

来源为真实公开行为，140,976次服务请求为规则模拟；无真实教学Agent或真实支持干预。
成绩可用时间是冻结假设，课程混合、多重比较及稀少正例限制均保留。
per_student.csv仅存于本机 var/results/mmfopda_gate0_oulad_20261113，不进入Git。
