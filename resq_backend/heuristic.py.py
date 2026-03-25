    def _fallback_aspect(self, w, h):
        aspect = w / max(h, 1.0)
        if aspect > 1.3: return "lying"
        if aspect < 0.8: return "standing"
        return "sitting"

    def _classify_pose(self, kpts, w, h) -> str:
        """Classify pose using keypoint geometry (Y coordinates, angles)."""
        if kpts is None or len(kpts) == 0:
            return self._fallback_aspect(w, h)
            
        kpts = np.asarray(kpts)
        if kpts.ndim == 3: kpts = kpts[0]
        if kpts.shape[0] < 17: return self._fallback_aspect(w, h)

        def get_pt(idx1, idx2):
            p1 = kpts[idx1] if kpts[idx1][2] > 0.3 else None
            p2 = kpts[idx2] if kpts[idx2][2] > 0.3 else None
            if p1 is None and p2 is None: return None
            if p1 is not None and p2 is not None:
                return ((p1[0]+p2[0])/2.0, (p1[1]+p2[1])/2.0)
            return p1[:2] if p1 is not None else p2[:2]

        neck   = get_pt(5, 6)
        pelvis = get_pt(11, 12)
        knee   = get_pt(13, 14)
        ankle  = get_pt(15, 16)
        
        aspect = w / max(h, 1.0)
        
        if not neck or not pelvis:
            return self._fallback_aspect(w, h)
            
        # Torso logic
        torso_dy = pelvis[1] - neck[1]
        torso_len = math.hypot(pelvis[0] - neck[0], torso_dy)
        if torso_len < 1.0: torso_len = 1.0
        
        # 1.0 = vertical, 0.0 = horizontal
        torso_verticality = torso_dy / torso_len  
        
        # 1. LYING
        if torso_verticality < 0.35:
            return "lying"

        # 2. SITTING vs STANDING
        leg_dy = 0
        leg_len = 0
        if ankle:
            leg_dy = ankle[1] - pelvis[1]
            leg_len = math.hypot(ankle[0] - pelvis[0], leg_dy)
        elif knee:
            leg_dy = knee[1] - pelvis[1]
            leg_len = math.hypot(knee[0] - pelvis[0], leg_dy)
            
        if leg_len > 1.0:
            leg_verticality = leg_dy / leg_len
            # Both torso and legs point clearly down
            if torso_verticality > 0.4 and leg_verticality > 0.4:
                return "standing" if aspect < 0.85 else "sitting"
            # Torso upright but legs are horizontal/tucked/pointed sideways
            elif torso_verticality > 0.4 and leg_verticality <= 0.4:
                return "sitting"
        
        # 3. Fallback without valid leg data
        if aspect < 0.85:
            return "standing"
        elif aspect > 1.1:
            if torso_verticality > 0.4:
                return "sitting"
            else:
                return "lying"
                
        return "sitting"