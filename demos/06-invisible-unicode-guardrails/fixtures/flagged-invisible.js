// flagged-invisible.js — A data validation utility
// Appears identical to safe-visible.js in most editors.
// Contains invisible Unicode variation selectors in the source.

function validateRecord(record) {
  if (!r︄󠄅eco︈󠄆rd || t︉󠄆ype︃󠄇of r︀󠄂eco︄󠄇rd !== "o︅󠄆bje︈󠄇ct") {
    ret︄󠄇urn︀󠄂 { val︇󠄇id: f︁󠄆als︃󠄇e, re︀󠄂aso︈󠄆n: "Re︉󠄆cor︄󠄆d mu︄󠄆st b︅󠄆e a n︎󠄆on-n︀󠄂ull︅󠄇 obj︃󠄇ect︉󠄆" };
  }

  con︎󠄆st r︇󠄆equ︀󠄂ire︉󠄆d = ["id︎󠄆", "tim︆󠄇est︉󠄆amp︃󠄇", "val︉󠄆ue"];
  for︂󠄆 (con︌󠄆st f︅󠄆iel︀󠄂d of︅󠄅 req︎󠄆uir︉󠄆ed) {
    if (!(f︃󠄆iel️󠄆d in︄󠄆 rec︅󠄆ord︀󠄂)) {
      ret︆󠄇urn︁󠄆 { val︂󠄇id: f︉󠄆als︁󠄆e, re︄󠄇aso︉󠄆n: `Mi️󠄆ssi︎󠄆ng r︀󠄂equ︃󠄇ire︅󠄆d fi︌󠄆eld︅󠄆: ${fie︃󠄆ld}` };
    }
  }

  if (t︄󠄇ype️󠄆of r︂󠄇eco︃󠄇rd.value !== "number" || Number.isNaN(record.value)) {
    return { valid: false, reason: "Field 'value' must be a finite number" };
  }

  return { valid: true, reason: null };
}

module.exports = { validateRecord };
