export function ForbiddenPage({ requiredLabel = 'another', onHome }) {
  return (
    <section className="role-panel">
      <h2 className="page-title">Forbidden</h2>
      <p>This view is for {requiredLabel} accounts.</p>
      <button type="button" className="btn-primary" onClick={onHome}>Go home</button>
    </section>
  );
}

export function NotFoundPage({ onHome }) {
  return (
    <section className="role-panel">
      <h2 className="page-title">Page not found</h2>
      <p>That address is not part of this demo.</p>
      <button type="button" className="btn-primary" onClick={onHome}>Go home</button>
    </section>
  );
}
