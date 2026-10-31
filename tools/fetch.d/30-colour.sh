# The colour study's sources (decision 8): Driller's colour versions, as
# disc images from the Internet Archive's software library. Nothing is
# extracted here: tools/colour/sources.py reads each executable out of its
# image in memory and checks it against ScummVM's detection entry.

# DOS, the PC's four drivers on one 360K disc (DRILLE.EXE is EGA).
getzip "$IA/driller-1989/Driller%20(1989).zip" DISK01.IMA \
    originals/dos/DISK01.IMA
# Amstrad CPC, the disc release (DRILL.BIN).
get "$IA/Driller_1987_Incentive_Software/Driller_1987_Incentive_Software.dsk" \
    originals/cpc/Driller.dsk
# Atari ST, the budget release (DRILLER/X.PRG), as TOSEC's CSM disc.
get "$IA/Driller_1988_Incentive_Software_cr_CSM/Driller_1988_Incentive_Software_cr_CSM.st" \
    originals/st/Driller.st
# Amiga, the 1988 release (DRILLER/driller and the data file it loads).
get "$IA/Driller_1988-09-27_MicroProse_cr_WOW_a_no_cracktro/Driller_1988-09-27_MicroProse_cr_WOW_a_no_cracktro.adf" \
    originals/amiga/Driller.adf
