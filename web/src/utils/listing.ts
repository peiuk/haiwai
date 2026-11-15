// 分类信息字段的中文名：发布表单和信息卡共用（后端 _ATTRS 的前端镜像）。
export const ATTR_FIELDS: Record<string, { key: string; label: string }[]> = {
  rent: [
    { key: "roomType", label: "房型" },
    { key: "moveIn", label: "入住时间" },
    { key: "bills", label: "Bills 是否包含" },
    { key: "deposit", label: "押金" },
    { key: "minTerm", label: "最短租期" },
  ],
  sale: [{ key: "roomType", label: "房型" }],
  commercial: [{ key: "roomType", label: "物业类型" }],
  secondhand: [
    { key: "condition", label: "成色" },
    { key: "pickup", label: "交易方式" },
  ],
  job: [
    { key: "jobType", label: "工作类型" },
    { key: "hours", label: "工作时间" },
  ],
};

export const KIND_LABEL: Record<string, string> = {
  rent: "出租",
  sale: "出售",
  commercial: "商业房产",
  secondhand: "二手",
  job: "招聘",
};

export function attrLabel(kind: string, key: string): string {
  return ATTR_FIELDS[kind]?.find((f) => f.key === key)?.label ?? key;
}
