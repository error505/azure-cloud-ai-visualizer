export const chooseHandle = (
  fromPos: { x: number; y: number },
  toPos: { x: number; y: number },
  role: 'source' | 'target'
) => {
  const dx = toPos.x - fromPos.x;
  const dy = toPos.y - fromPos.y;
  const angle = Math.atan2(dy, dx);
  const PI = Math.PI;
  if (angle > -PI / 4 && angle <= PI / 4) {
    return `right-${role}`;
  }
  if (angle > PI / 4 && angle <= (3 * PI) / 4) {
    return `bottom-${role}`;
  }
  if (angle > (3 * PI) / 4 || angle <= -((3 * PI) / 4)) {
    return `left-${role}`;
  }
  return `top-${role}`;
};

export default chooseHandle;
