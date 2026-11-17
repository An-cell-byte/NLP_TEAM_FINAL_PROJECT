"""Operaciones deterministas sobre filas tipadas; nunca evalúa expresiones o SQL libre."""
from decimal import Decimal,InvalidOperation
import json
OPS={'count','sum','mean','max','min','rows'};COMPARISONS={'eq','ne','gt','ge','lt','le'}
def match(row,filters):
 for f in filters:
  col=f['column'];op=f.get('op','eq');expected=f.get('value')
  if col not in row['values'] or op not in COMPARISONS:raise ValueError('Filtro o columna no admitido.')
  v=row['values'][col]
  if row['types'].get(col)=='decimal' and v is not None and expected is not None:
   try:v=Decimal(str(v));expected=Decimal(str(expected))
   except InvalidOperation:raise ValueError('El filtro numérico no es válido.') from None
  if v is None or expected is None:
   valid=(v is expected) if op=='eq' else (v is not expected) if op=='ne' else False
  else:
   try:valid={'eq':lambda:v==expected,'ne':lambda:v!=expected,'gt':lambda:v>expected,'ge':lambda:v>=expected,'lt':lambda:v<expected,'le':lambda:v<=expected}[op]()
   except TypeError:raise ValueError('El filtro no coincide con el tipo de la columna.') from None
  if not valid:return False
 return True

def calculate(table,operation,column=None,filters=None,limit=100):
 if operation not in OPS:raise ValueError('Operación admitida: count, sum, mean, min, max o rows.')
 if not 1<=limit<=100:raise ValueError('El límite de salida debe estar entre 1 y 100.')
 if len(filters or [])>10:raise ValueError('Máximo diez filtros.')
 if column is not None and column not in table['columns']:raise ValueError('La columna no existe.')
 for f in filters or []:
  if not isinstance(f,dict):raise ValueError('Cada filtro debe ser un objeto con column, op y value.')
  if f.get('column') not in table['columns']:raise ValueError('La columna del filtro no existe.')
 rows=[r for r in table['rows'] if match(r,filters or [])];missing=0
 if operation=='count':value=len(rows)
 elif operation=='rows':value=[r['values'] for r in rows[:limit]]
 else:
  if not column:raise ValueError('Indica la columna que quieres calcular.')
  numbers=[]
  for r in rows:
   v=r['values'][column]
   if v is None:missing+=1;continue
   if r['types'].get(column)!='decimal':raise ValueError('La columna contiene valores no numéricos.')
   numbers.append(Decimal(str(v)))
  if not numbers:value=None
  elif operation=='sum':value=str(sum(numbers,Decimal(0)))
  elif operation=='mean':value=str(sum(numbers,Decimal(0))/len(numbers))
  elif operation=='max':value=str(max(numbers))
  else:value=str(min(numbers))
 return {'kind':'calculo_determinista','available_columns':table['columns'],'unit':table.get('units',{}).get(column),'unit_note':'La unidad solo se muestra si la fuente la declara; no se infiere ni se convierte.','operation':operation,'column':column,'filters':filters or [],'result':value,'matched_rows':len(rows),'missing_values_excluded':missing,'scope':'Filas autorizadas que cumplen los filtros; count cuenta filas, no valores presentes.','locations':[r['location'] for r in rows[:limit]],'locations_truncated':len(rows)>limit}


def render_answer(result, *, group_by=None, variant=0):
    """Redacta el resultado calculado sin repetir los datos de diagnóstico."""
    dataset = result.get('source', {}).get('dataset', '').rsplit('.', 1)[-1]
    loans = dataset == 'prestamos_detalle'
    filters = result.get('filters', [])
    name_filters = [f['value'] for f in filters if f['column'] == 'nombre' and f.get('op', 'eq') == 'eq' and f.get('value')]
    person = str(name_filters[0]).strip() if loans and len(name_filters) == 1 else ''
    filtered = len(filters) > 1 if person else bool(filters)

    if 'groups' not in result:
        return _render_value(result, result['result'], loans, person, filtered, variant=variant)
    if not result['groups']:
        return 'No encontré préstamos para agrupar.' if loans else 'No encontré registros para agrupar.'

    answers = []
    for group in result['groups']:
        label = group['group']
        name = str(label).strip() if loans and group_by == 'nombre' and label is not None else ''
        answer = _render_value(result, group['result'], loans, name, bool(filters), variant=variant, grouped=True)
        if not name:
            title = str(label) if label is not None else 'Sin dato de agrupación'
            answer = f'**{title}**\n\n{answer}'
        answers.append(answer)
    return '\n\n'.join(answers)


def _render_value(result, value, loans, person, filtered, *, variant=0, grouped=False):
    operation = result['operation']
    quantity = value
    if operation == 'rows':
        quantity = len(value) if grouped else result['matched_rows']
    noun = ('préstamo' if quantity == 1 else 'préstamos') if loans else ('registro' if quantity == 1 else 'registros')
    name = person[:1].upper() + person[1:]
    subject = f' de {name}' if name else ''
    matches = ' que coincide con tu búsqueda' if quantity == 1 else ' que coinciden con tu búsqueda'

    if operation in {'count', 'rows'} and not value:
        if variant:
            return f'La búsqueda no devolvió {noun}{subject}.'
        detail = ' para esa búsqueda' if filtered else ''
        return f'No encontré {noun}{subject}{detail}.'
    if operation == 'count':
        if person and not filtered:
            return f'Encontré {value} {noun}{subject}.' if variant else f'{name} tiene {value} {noun}.'
        if filtered:
            if variant:
                return f'Tu búsqueda devuelve {value} {noun}{subject}.'
            return f'Encontré {value} {noun}{subject}{matches}.'
        return f'En total hay {value} {noun}.' if variant else f'Hay {value} {noun}.'

    if operation == 'rows':
        detail = f'{quantity} {noun}{subject}{matches if filtered else ""}'
        if variant and quantity > len(value):
            description = f'De los {detail}, aquí puedes ver {len(value)}.'
        elif variant:
            description = f'Aquí tienes el detalle de {detail}.'
        else:
            description = f'Encontré {detail}.'
        if not variant and quantity > len(value):
            description += f' Aquí puedes ver {len(value)}.'
        return description + '\n\n' + _render_table(value)

    column = result['column'].replace('_', ' ')
    if value is None:
        if variant:
            return f'Para ese cálculo faltan valores de {column}.'
        return f'No encontré valores de {column} para hacer el cálculo.'
    label = {'sum': 'total', 'mean': 'promedio', 'min': 'mínimo', 'max': 'máximo'}[operation]
    metric = f'El importe {label}' if column == 'importe' else f'El {label} de {column}'
    scope = f' de los préstamos{subject}' if loans else ''
    if filtered:
        scope += ' que coinciden con tu búsqueda' if loans else ' de los registros que coinciden con tu búsqueda'
    unit = f' {result["unit"]}' if result.get('unit') else ''
    metric_phrase = metric[:1].lower() + metric[1:]
    answer = f'{value}{unit} es {metric_phrase}{scope}.' if variant else f'{metric}{scope} es de {value}{unit}.'
    missing = 0 if grouped else result['missing_values_excluded']
    if missing and operation == 'mean':
        present = result['matched_rows'] - missing
        available = 'valor disponible' if present == 1 else 'valores disponibles'
        answer += f' Lo calculé con {present} {available}.'
    return answer


def _render_table(rows):
    columns = list(rows[0])

    def cell(value):
        value = 'Sin dato' if value is None else str(value)
        return ' '.join(value.splitlines()).replace('\\', '\\\\').replace('|', '\\|')

    def line(values):
        return '| ' + ' | '.join(cell(value) for value in values) + ' |'

    headings = {'id': 'ID', 'usuario_id': 'ID de usuario'}
    return '\n'.join([
        line(headings.get(column, column.replace('_', ' ').capitalize()) for column in columns),
        line('---' for _ in columns),
        *(line(row.get(column) for column in columns) for row in rows),
    ])
