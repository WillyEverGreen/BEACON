const express = require("express");
const { enqueueAudit, getAuditStatus } = require("../controllers/audit.controller");

const router = express.Router();

router.post("/audit", enqueueAudit);
router.get("/audit/:job_id", getAuditStatus);

module.exports = router;
