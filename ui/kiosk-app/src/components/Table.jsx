export function Table({ columns, rows }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-white">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-line text-left">
          <thead className="bg-slate-50">
            <tr>
              {columns.map((column) => (
                <th
                  className="whitespace-nowrap px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted"
                  key={column.key}
                  scope="col"
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row) => (
              <tr className="transition hover:bg-slate-50" key={row.id}>
                {columns.map((column) => (
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-700" key={column.key}>
                    {column.render ? column.render(row) : row[column.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
