const express = require("express");
const { getResults } = require("../controllers/results.controller");

const router = express.Router();

router.get("/results/:job_id", getResults);

module.exports = router;
