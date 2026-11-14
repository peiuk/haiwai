<template>
  <!-- 与原型 prototype-x-style.html 同源的 SVG sprite；全局只挂载一次（App.vue）。
       i-up / i-down 为正式前端新增的排序箭头，其余 symbol 与原型逐字一致。 -->
  <svg class="icon-sprite" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"
       style="position:absolute;width:0;height:0;overflow:hidden">
    <symbol id="i-home" viewBox="0 0 24 24"><path d="M3 10.5 12 3l9 7.5V21H3z"/></symbol>
    <symbol id="i-plus" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></symbol>
    <symbol id="i-search" viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></symbol>
    <symbol id="i-heart" viewBox="0 0 24 24"><path d="M12 20s-8-4.7-8-10a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 5.3-8 10-8 10z"/></symbol>
    <symbol id="i-heart-fill" viewBox="0 0 24 24"><path fill="currentColor" stroke="none" d="M12 20s-8-4.7-8-10a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 5.3-8 10-8 10z"/></symbol>
    <symbol id="i-grid" viewBox="0 0 24 24"><path d="M4 4h16v16H4zM4 10h16M10 4v16"/></symbol>
    <symbol id="i-circle" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/></symbol>
    <symbol id="i-theme" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z"/></symbol>
    <symbol id="i-phone" viewBox="0 0 24 24"><rect x="7" y="2.5" width="10" height="19" rx="2"/><path d="M10.5 5.5h3"/></symbol>
    <symbol id="i-menu" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></symbol>
    <symbol id="i-reply" viewBox="0 0 24 24"><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H8l-5 2 1.6-4.8A8.5 8.5 0 1 1 21 11.5z"/></symbol>
    <symbol id="i-repost" viewBox="0 0 24 24"><path d="M4 8h13l-3.2-3.2M20 16H7l3.2 3.2"/></symbol>
    <symbol id="i-bookmark" viewBox="0 0 24 24"><path d="M6 3.5h12v17l-6-4.2-6 4.2z"/></symbol>
    <symbol id="i-bookmark-fill" viewBox="0 0 24 24"><path fill="currentColor" stroke="none" d="M6 3.5h12v17l-6-4.2-6 4.2z"/></symbol>
    <symbol id="i-share" viewBox="0 0 24 24"><path d="M12 15V3m0 0L8 7m4-4 4 4M4 13v7h16v-7"/></symbol>
    <symbol id="i-flag" viewBox="0 0 24 24"><path d="M5 21V4m0 0h13l-2.2 4L18 12H5"/></symbol>
    <symbol id="i-more" viewBox="0 0 24 24"><path d="M5 12h.01M12 12h.01M19 12h.01"/></symbol>
    <symbol id="i-spark" viewBox="0 0 24 24"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/></symbol>
    <symbol id="i-settings" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M18.7 5.3l-1.4 1.4M6.7 17.3l-1.4 1.4"/></symbol>
    <symbol id="i-mute" viewBox="0 0 24 24"><path d="M4 9h3l4-3.5v13L7 15H4zM15 9l5 6M20 9l-5 6"/></symbol>
    <symbol id="i-check" viewBox="0 0 24 24"><path d="M4 12.5 9 17.5 20 6.5"/></symbol>
    <symbol id="i-chev" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></symbol>
    <symbol id="i-pin" viewBox="0 0 24 24"><path d="M9 3h6l-1 6 3 3v2H7v-2l3-3zM12 14v7"/></symbol>
    <symbol id="i-globe" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></symbol>
    <symbol id="i-link" viewBox="0 0 24 24"><path d="M9 15l6-6M8.5 12.5l-2 2a3 3 0 0 0 4.2 4.2l2-2M15.5 11.5l2-2a3 3 0 0 0-4.2-4.2l-2 2"/></symbol>
    <symbol id="i-close" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></symbol>
    <symbol id="i-image" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9" r="1.5"/><path d="m4 17 5-5 3.5 3.5 2.5-2.5 5 5"/></symbol>
    <symbol id="i-video" viewBox="0 0 24 24"><rect x="3" y="5" width="13" height="14" rx="2"/><path d="m16 10 5-3v10l-5-3z"/></symbol>
    <symbol id="i-play" viewBox="0 0 24 24"><path d="m8 5 11 7-11 7z"/></symbol>
    <symbol id="i-hash" viewBox="0 0 24 24"><path d="M5 9h14M4 15h14M10 3 8 21M17 3l-2 18"/></symbol>
    <symbol id="i-at" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 5 2 9 9 0 1 0-3 5"/></symbol>
    <symbol id="i-bell" viewBox="0 0 24 24"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></symbol>
    <symbol id="i-mail" viewBox="0 0 24 24"><path d="M3 6h18v12H3zM3 7l9 6 9-6"/></symbol>
    <symbol id="i-user" viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></symbol>
    <symbol id="i-back" viewBox="0 0 24 24"><path d="M19 12H5M12 19l-7-7 7-7"/></symbol>
    <symbol id="i-feather" viewBox="0 0 24 24"><path d="M4 20 14 10M20 4c-6 0-12 4-12 12h4c6 0 8-6 8-12z"/></symbol>
    <symbol id="i-up" viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7"/></symbol>
    <symbol id="i-down" viewBox="0 0 24 24"><path d="M12 5v14M5 12l7 7 7-7"/></symbol>
  </svg>
</template>
