/* Immutable series bytes from the pinned original VSOP2013 EMB source. */
#ifdef __APPLE__
.section __TEXT,__const
.p2align 3
.private_extern _fatebridge_vsop_series
_fatebridge_vsop_series:
.incbin "emb-series.bin"
.private_extern _fatebridge_vsop_series_end
_fatebridge_vsop_series_end:
#else
.section .rodata
.p2align 3
.hidden fatebridge_vsop_series
.global fatebridge_vsop_series
fatebridge_vsop_series:
.incbin "emb-series.bin"
.hidden fatebridge_vsop_series_end
.global fatebridge_vsop_series_end
fatebridge_vsop_series_end:
.section .note.GNU-stack,"",@progbits
#endif
