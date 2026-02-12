import { classNames } from '../utils';

interface StatusBadgeProps {
  className: string;
  children: React.ReactNode;
  dot?: boolean;
  dotColor?: string;
}

export function StatusBadge({ className, children, dot, dotColor }: StatusBadgeProps) {
  return (
    <span className={classNames(className, 'inline-flex items-center gap-1.5')}>
      {dot && <span className={classNames('h-1.5 w-1.5 rounded-full', dotColor)} />}
      {children}
    </span>
  );
}
