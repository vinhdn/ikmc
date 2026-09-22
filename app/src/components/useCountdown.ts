import { useEffect, useRef, useState } from 'react';

/**
 * Bộ đếm ngược. Gọi onExpire khi hết giờ.
 * @param seconds Tổng số giây
 * @param active Có chạy hay không
 */
export function useCountdown(
  seconds: number,
  active: boolean,
  onExpire: () => void,
) {
  const [remaining, setRemaining] = useState(seconds);
  const expireRef = useRef(onExpire);
  expireRef.current = onExpire;

  useEffect(() => {
    setRemaining(seconds);
  }, [seconds]);

  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          clearInterval(id);
          expireRef.current();
          return 0;
        }
        return r - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [active]);

  return remaining;
}

export function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}
