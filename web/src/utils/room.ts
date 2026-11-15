// 房间类型选项：创建房间（ProfileView）和房主改房间（RoomView）共用。
export const ROOM_TYPES = [
  { value: "general", label: "综合讨论" },
  { value: "series", label: "剧集系列" },
  { value: "film", label: "电影" },
  { value: "video", label: "视频" },
] as const;
