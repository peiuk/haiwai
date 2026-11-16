// 房间类型选项：创建房间（ProfileView）和房主改房间（RoomView）共用；叫法和后端 app/rooms.py 的 ROOM_TYPE_LABELS 保持一致。
export const ROOM_TYPES = [
  { value: "general", label: "综合讨论" },
  { value: "series", label: "剧集系列" },
  { value: "film", label: "电影" },
  { value: "video", label: "视频" },
] as const;
