从候选餐厅中选出适合当前行程的索引。

最终推荐数：$final_needed
候选池目标数：$candidate_target

规则：
1. 只返回索引，不要重写字段。
2. 每天推荐约 2 家有特色的餐厅，优先保留本地特色、评分更高、图片更完整、介绍更清晰的候选。
3. 尽量覆盖 lunch / dinner / snack 等不同场景，不要全部集中在同一类。
4. 去掉明显重复或信息太弱的候选。
5. 如果可用候选数不少于候选池目标数，你必须返回恰好 $candidate_target 个不重复索引。
6. 如果可用候选数少于候选池目标数，你必须返回全部可用索引，并将 is_sufficient 设为 false。

$retry_instruction

候选上下文 JSON：
$context_json

只返回 JSON：
{
  "selected_indexes": [0, 3, 5],
  "is_sufficient": true,
  "reason": "一句话说明"
}
