/* Shared by the webview and Node tests. No VS Code or DOM dependencies. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.MochiModel = factory();
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const DEFAULT_POSITION = { x: 0.5, y: 0.8 };
  function clampPosition(position) {
    if (!position || !Number.isFinite(position.x) || !Number.isFinite(position.y)) return { ...DEFAULT_POSITION };
    return { x: Math.max(0, Math.min(1, position.x)), y: Math.max(0, Math.min(1, position.y)) };
  }
  function sanitizeState(raw) {
    return { sleeping: raw?.sleeping === true, position: clampPosition(raw?.position) };
  }
  function duration(animation) {
    return animation.durations_ms?.reduce((a, b) => a + b, 0) ?? animation.frame_count * Math.round(1000 / animation.fps);
  }
  function frameAt(animation, elapsed) {
    const total = duration(animation);
    let time = Math.max(0, elapsed);
    if (!animation.loop && time >= total) return { index: animation.frame_count - 1, done: true };
    time %= total;
    for (let index = 0; index < animation.frame_count; index++) {
      const step = animation.durations_ms?.[index] ?? Math.round(1000 / animation.fps);
      if (time < step) return { index, done: false };
      time -= step;
    }
    return { index: 0, done: false };
  }
  function dragPose(velocity, previous = 'neutral') {
    const speed = Math.abs(velocity) / 600;
    const side = velocity < 0 ? 'left' : 'right';
    if (speed < 0.1) return 'neutral';
    const medium = previous === `${side}_medium` ? speed >= 0.16 : speed >= 0.22;
    return `${side}_${medium ? 'medium' : 'soft'}`;
  }
  class Companion {
    constructor(manifest, state) {
      this.manifest = manifest;
      this.state = sanitizeState(state);
      this.animation = this.state.sleeping ? 'sleeping' : 'idle';
      this.started = 0;
      this.held = false;
      this.pose = 'neutral';
      this.releaseSide = null;
      this.lastActivity = null;
      this.nextBlink = 8000;
    }
    play(name, now) { this.animation = name; this.started = now; }
    snapshot() { return sanitizeState(this.state); }
    pet(now) {
      if (this.held) return;
      this.lastActivity = null;
      if (this.state.sleeping) { this.state.sleeping = false; this.play('wake', now); }
      else this.play('heart', now);
    }
    toggleSleep(now) {
      this.held = false;
      this.lastActivity = null;
      this.state.sleeping = !this.state.sleeping;
      this.play(this.state.sleeping ? 'sleep' : 'wake', now);
    }
    activity(now, enabled) {
      if (!enabled || this.state.sleeping || this.held) return;
      if (!['idle', 'blink', 'typing_intro', 'typing_loop', 'typing_outro'].includes(this.animation)) return;
      this.lastActivity = now;
      if (!['typing_intro', 'typing_loop'].includes(this.animation)) this.play('typing_intro', now);
    }
    stopTyping(now) {
      this.lastActivity = null;
      if (['typing_intro', 'typing_loop'].includes(this.animation)) this.play('typing_outro', now);
    }
    beginDrag(now) {
      this.held = true;
      this.pose = 'neutral';
      this.releaseSide = null;
      this.lastActivity = null;
      if (this.state.sleeping) { this.state.sleeping = false; this.play('wake', now); }
      else this.play('pickup', now);
    }
    drag(velocity, now) {
      if (!this.held) return;
      this.pose = dragPose(velocity, this.pose);
      this.tick(now);
    }
    endDrag(now, cancelled = false) {
      if (!this.held) return;
      this.held = false;
      this.releaseSide = this.pose.startsWith('left') ? 'left' : this.pose.startsWith('right') ? 'right' : null;
      this.play(cancelled ? 'drop' : 'settle', now);
    }
    tick(now) {
      if (this.lastActivity !== null && now - this.lastActivity >= 4000 && ['typing_intro', 'typing_loop'].includes(this.animation)) {
        const expired = this.lastActivity + 4000;
        this.lastActivity = null;
        this.play('typing_outro', expired);
      }
      for (let i = 0; i < 8; i++) {
        if (this.animation === 'settle') {
          const elapsed = now - this.started;
          if (elapsed >= 210) { this.play('drop', this.started + 210); continue; }
          const side = elapsed < 70 && this.releaseSide ? this.releaseSide : 'neutral';
          return { animation: 'dragged', path: `drag/drag_settle_${side}.png`, index: 0 };
        }
        if (this.animation === 'dragged') return { animation: 'dragged', path: `drag/drag_${this.pose}.png`, index: 0 };
        const data = this.manifest.animations[this.animation];
        const frame = frameAt(data, now - this.started);
        if (!frame.done) {
          if (this.animation === 'idle' && now >= this.nextBlink) { this.play('blink', now); this.nextBlink = now + 8000; continue; }
          return { animation: this.animation, index: frame.index, path: data.frames?.[frame.index] ?? data.spritesheet };
        }
        const finished = this.started + duration(data);
        const next = this.animation === 'sleep' ? 'sleeping'
          : this.animation === 'wake' && this.held ? 'pickup'
          : this.animation === 'pickup' && this.held ? 'dragged'
          : this.animation === 'typing_intro' && this.lastActivity !== null ? 'typing_loop'
          : 'idle';
        this.play(next, finished);
      }
      this.play(this.state.sleeping ? 'sleeping' : 'idle', now);
      return this.tick(now);
    }
  }
  return { clampPosition, sanitizeState, frameAt, dragPose, Companion };
});
