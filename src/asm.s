; Star Frag 3D - hot paths in Z80 asm (from Splat Trooper 3D)
;
; Each view is 16 tile columns x 12 tile rows.  Only the TOP 6 rows are ever
; built: the bottom 6 rows of the name table point at the same tiles with the
; vertical-flip bit and the sprite palette (which holds floor colours where the
; BG palette holds sky colours).  So every wall column costs half the work and
; half the VRAM bandwidth.
;
; One tile column = 2 rays of 4 px.  COLBUF (0xD700) gets one byte per pixel
; row: high nibble = left ray colour, low nibble = right ray colour.  The LUT
; (0xD800, 4 pages) turns that byte into the 4 bitplane bytes of a tile row.

	.module asm
	.area _DATA
_mq_a::	.ds 1
_mq_b::	.ds 2
_mq_r::	.ds 2
_rd_bank::	.ds 1
_rd_l::	.ds 1
_rd_y0::	.ds 1
_rd_rows::	.ds 2
_rd_vaddr::	.ds 2

	.area _CODE
	.globl dl_body
	.globl dr_body

; u16 mul8(u8 a /*A*/, u16 b /*DE*/) -> (a*b)>>8 in DE   (clobbers HL BC)
; Quarter-square multiply: x*y = f(x+y) - f(|x-y|), f(n) = n*n/4, with f
; split into a low-byte table at 0xD000 and a high-byte table at 0xD200
; (512 entries each, built by qsq_init).
_mul8::
	ld	b,a
	ld	c,d		; c = high byte of b
	sub	e
	jr	nc,1$
	neg
1$:	ld	l,a
	ld	h,#0xD0
	ld	a,b
	add	a,e
	ld	e,a
	ld	a,#0xD0
	adc	a,#0
	ld	d,a
	ld	a,(de)
	sub	(hl)
	inc	d
	inc	d
	inc	h
	inc	h
	ld	a,(de)
	sbc	a,(hl)
	ld	e,a		; e = (a * b.lo) >> 8
	ld	a,b
	sub	c
	jr	nc,2$
	neg
2$:	ld	l,a
	ld	h,#0xD0
	ld	a,b
	add	a,c
	ld	c,a
	ld	a,#0xD0
	adc	a,#0
	ld	b,a
	ld	a,(bc)
	sub	(hl)
	ld	d,a		; low byte of a * b.hi
	inc	b
	inc	b
	inc	h
	inc	h
	ld	a,(bc)
	sbc	a,(hl)
	ld	h,a
	ld	a,d
	add	a,e
	ld	e,a
	ld	a,h
	adc	a,#0
	ld	d,a
	ret

; void qsq_init(void): build the quarter-square tables
_qsq_init::
	ld	hl,#0		; f
	ld	de,#0		; x
3$:	; store f at 0xD000+x (lo) and 0xD200+x (hi)
	push	hl
	ld	a,d
	add	a,#0xD0
	ld	b,a
	ld	c,e
	ld	a,l
	ld	(bc),a
	inc	b
	inc	b
	ld	a,h
	ld	(bc),a
	pop	hl
	; f += (x+1) >> 1
	inc	de
	ld	b,d
	ld	c,e
	srl	b
	rr	c
	add	hl,bc
	ld	a,d
	cp	#2
	jr	c,3$
	ret

; void mulq(void): mq_r = (mq_a * mq_b) >> 8
_mulq::
	ld	a,(_mq_a)
	ld	de,(_mq_b)
	call	_mul8
	ld	(_mq_r),de
	ret

; void draw_left(void)
;   rd_bank: texture bank, rd_l: column id inside the bank pages,
;   rd_rows: row-table entry (48 page bytes), rd_y0: first row to build
;   Writes COLBUF[y0..47] = shifted colour (left ray -> high nibble)
_draw_left::
	ld	a,(_rd_bank)
	ld	(0xFFFF),a
	ld	a,(_rd_y0)
	ld	e,a
	ld	d,#0xD7
	ld	hl,(_rd_rows)
	ld	c,a
	ld	b,#0
	add	hl,bc
	ld	b,h
	ld	c,l
	ld	l,a
	ld	h,#0
	add	hl,hl
	add	hl,hl
	add	hl,hl
	push	de
	ld	de,#dl_body
	add	hl,de
	pop	de
	push	hl
	ld	a,(_rd_l)
	ld	l,a
	ret				; jump into the unrolled body

; void draw_right(void): COLBUF[y] |= colour (right ray -> low nibble)
_draw_right::
	ld	a,(_rd_bank)
	ld	(0xFFFF),a
	ld	a,(_rd_y0)
	ld	e,a
	ld	d,#0xD7
	ld	hl,(_rd_rows)
	ld	c,a
	ld	b,#0
	add	hl,bc
	push	hl			; rows + y0
	ld	l,a
	ld	h,#0
	add	hl,hl
	add	hl,hl
	add	hl,hl
	or	a
	sbc	hl,bc			; y0*7
	ld	bc,#dr_body
	add	hl,bc
	pop	bc			; bc = rows + y0
	push	hl
	ld	a,(_rd_l)
	ld	l,a
	ret

; void out_column(void): COLBUF[y0..47] -> VRAM at rd_vaddr, paced for
; active display (>= 27 cycles between data port writes)
_out_column::
	ld	hl,(_rd_vaddr)
	di
	ld	a,l
	out	(0xBF),a
	ld	a,h
	out	(0xBF),a
	ei
	ld	a,(_rd_y0)
	ld	e,a
	ld	d,#0xD7
	neg
	add	a,#48
	ret	z
	ld	b,a
	ld	c,#0xBE
3$:	ld	a,(de)
	ld	l,a
	ld	h,#0xD8
	ld	a,(hl)
	out	(c),a
	inc	h
	ld	a,(hl)
	inc	e
	out	(c),a
	inc	h
	ld	a,(hl)
	nop
	out	(c),a
	inc	h
	ld	a,(hl)
	nop
	out	(c),a
	djnz	3$
	ret

; ---------------------------------------------------------------- sprite projection
	.area _DATA
_pj_dx::	.ds 2
_pj_dy::	.ds 2
_pj_ca::	.ds 1
_pj_sa::	.ds 1
_pj_cf::	.ds 1
_pj_depth::	.ds 2
_pj_lat::	.ds 2
	.area _CODE

; HL = v (s16), A = |c|, B bit0 = sign(c)  ->  DE = (v*c) >> 8 (signed)
smul_a:
	bit	7,h
	jr	z,1$
	ld	c,a
	xor	a
	sub	l
	ld	l,a
	sbc	a,a
	sub	h
	ld	h,a
	ld	a,c
	inc	b
1$:	ex	de,hl
	push	bc
	call	_mul8
	pop	bc
	bit	0,b
	ret	z
	xor	a
	sub	e
	ld	e,a
	sbc	a,a
	sub	d
	ld	d,a
	ret

; depth = dx*cos + dy*sin ; lat = dy*cos - dx*sin   (all >> 8)
; project_d: the same, but returns right after depth when the point is
; closer than 64 (1/4 tile) or behind the camera (pj_lat is then not set)
	.area _DATA
pj_early:	.ds 1
	.area _CODE
_project_d::
	ld	a,#1
	jr	pj_go
_project::
	xor	a
pj_go:
	ld	(pj_early),a
	ld	a,(_pj_cf)
	and	#1
	ld	b,a
	ld	hl,(_pj_dx)
	ld	a,(_pj_ca)
	call	smul_a
	push	de
	ld	a,(_pj_cf)
	rrca
	and	#1
	ld	b,a
	ld	hl,(_pj_dy)
	ld	a,(_pj_sa)
	call	smul_a
	pop	hl
	add	hl,de
	ld	(_pj_depth),hl
	ld	a,(pj_early)
	or	a
	jr	z,pj_lat
	bit	7,h
	ret	nz
	ld	a,h
	or	a
	jr	nz,pj_lat
	ld	a,l
	cp	#64
	ret	c
pj_lat:
	ld	a,(_pj_cf)
	and	#1
	ld	b,a
	ld	hl,(_pj_dy)
	ld	a,(_pj_ca)
	call	smul_a
	push	de
	ld	a,(_pj_cf)
	rrca
	and	#1
	ld	b,a
	ld	hl,(_pj_dx)
	ld	a,(_pj_sa)
	call	smul_a
	pop	hl
	or	a
	sbc	hl,de
	ld	(_pj_lat),hl
	ret
