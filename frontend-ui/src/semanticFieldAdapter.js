/**
 * Frontend adapter for optional semantic metadata.
 *
 * Physical field values remain the canonical selection values so existing
 * reports and query payloads stay backward compatible. Semantic metadata only
 * changes labels/default aggregation and adds semantic_dataset_id when present.
 */
export function getSemanticFields(dataset) {
  const source = dataset?.semantic || dataset?.semantic_model || dataset?.semanticModel || {};
  const fields = [];

  const add = (items, role) => {
    if (!Array.isArray(items)) return;
    items.forEach((item) => {
      const physicalField = item?.physical_field || item?.physicalField || item?.field || item?.name;
      if (!physicalField) return;
      fields.push({
        name: String(item?.name || physicalField),
        physicalField: String(physicalField),
        role: item?.role || role || "attribute",
        dataType: item?.data_type || item?.dataType || "unknown",
        displayName: item?.display_name || item?.displayName || item?.name || physicalField,
        defaultAggregation: item?.default_aggregation || item?.defaultAggregation || null,
      });
    });
  };

  add(dataset?.semantic_dimensions || dataset?.semanticDimensions || source?.dimensions, "dimension");
  add(dataset?.semantic_measures || dataset?.semanticMeasures || source?.measures, "measure");
  add(source?.fields, null);

  const seen = new Set();
  return fields.filter((item) => {
    const key = `${item.physicalField}::${item.name}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function buildSemanticFieldMap(dataset) {
  return new Map(getSemanticFields(dataset).map((item) => [item.physicalField, item]));
}

export function getSemanticDatasetId(dataset) {
  return (
    dataset?.semantic_dataset_id ||
    dataset?.semanticDatasetId ||
    dataset?.semantic?.id ||
    dataset?.semantic_model_id ||
    dataset?.semanticModelId ||
    ""
  );
}

export function getSemanticFieldLabel(dataset, physicalField) {
  const item = buildSemanticFieldMap(dataset).get(physicalField);
  if (!item) return physicalField;
  return item.displayName && item.displayName !== physicalField
    ? `${item.displayName} (${physicalField})`
    : item.displayName;
}

export function getDefaultAggregation(dataset, physicalField) {
  return buildSemanticFieldMap(dataset).get(physicalField)?.defaultAggregation || null;
}


export function normalizeSemanticMetadata(payload) {
  const model = payload?.semantic_model || payload?.semanticModel || payload?.model || {};
  const datasets = Array.isArray(model?.datasets) ? model.datasets : [];
  const dataset = datasets[0] || payload?.semantic || null;
  const fields = getSemanticFields({ semantic: dataset || {} });
  const consistency = payload?.consistency || {};
  return {
    model,
    dataset,
    fields,
    semanticDatasetId: payload?.semantic_dataset_id || dataset?.id || "",
    consistent: consistency.consistent !== false,
    consistency,
  };
}
