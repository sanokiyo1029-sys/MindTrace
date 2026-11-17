import Icon from './Icon.jsx';
import PaperSurface from './PaperSurface.jsx';

export function PageHeading({ eyebrow, title, description, action }) { return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>; }
export function Button({ children, variant = 'primary', icon, className = '', ...props }) { return <button className={`button ${variant} ${className}`} {...props}>{icon && <Icon name={icon} size={17} />}{children}</button>; }
export function Panel({ children, className = '', interactive = false }) {
  if (interactive) return <PaperSurface className={`panel ${className}`}>{children}</PaperSurface>;
  return <section className={`panel ${className}`}>{children}</section>;
}
